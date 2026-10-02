"""
engine.py -- EVENT SCHEDULING MODULE  (Figure 2, box 2 of the paper).

A from-scratch discrete-event simulation core built on ``heapq``.  No SimPy,
no black-box process library: every state transition is explicit so that the
mechanism is auditable, which is the whole point of the exercise.

Event types and what each one does
----------------------------------
  SHIFT_CHANGE        R(t) changes -> re-dispatch (a bigger shift may free
                      capacity; a smaller one never interrupts service)
  ARRIVAL             patient joins W_init,3 or W_init,4 -> re-dispatch
  CONSULT_END         physician released; patient either enters diagnostics,
                      joins the follow-up queue path, or is discharged
                      -> re-dispatch
  EXAM_DEVICE_FREE    a modality finishes occupying its device; the next exam
                      of the same patient starts, and the device's own FIFO
                      queue is pulled
  EXAM_RESULTS_READY  all of a patient's results are in (Eq. 4) -> patient
                      joins W_follow -> re-dispatch

The dispatch step
-----------------
``_dispatch(now)`` asks the *policy* which patients start service, given the
number of currently free physicians.  This single call site is where every
scheduling strategy plugs in -- IFP, ALT, SBP, WSEPT and Gc-mu all differ only
in what ``Policy.allocate`` returns.
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import TYPE_CHECKING, Callable, Deque, List, Optional, Sequence

from . import config as C
from .entities import (EVT_PAYLOAD, EVT_TIME, EVT_TYPE, EventType, Patient,
                       QueueId, Stage, new_event)
from .policies import Policy
from .resources import DeviceBank, PhysicianPool

if TYPE_CHECKING:                      # import only for the type annotation
    from .metrics import RunResult


class Simulation:
    """One replication: one patient stream x one policy x one configuration."""

    def __init__(self, cfg: C.SimConfig, policy: Policy,
                 patients: Sequence[Patient],
                 trace: Optional[Callable[[float, str, str], None]] = None):
        self.cfg = cfg
        self.policy = policy
        self.policy.bind(cfg)
        self.patients: List[Patient] = list(patients)
        self.trace = trace

        self.now = 0.0
        self.fel: List = []                       # future-event list (a heap)
        self.pool = PhysicianPool(cfg.shifts)
        self.bank = DeviceBank(cfg.modalities)

        # the three competing queues of paper Sec 2.1.4
        # standing counts of what physicians are busy with (ALT needs these)
        self.busy_initial = 0
        self.busy_follow = 0

        self.q3: Deque[Patient] = deque()         # W^t_init,3
        self.q4: Deque[Patient] = deque()         # W^t_init,4
        self.qf: Deque[Patient] = deque()         # W^t_follow

        # time-series recorders (used by the demo / queue-length figures)
        self.queue_history: List = []             # (t, len3, len4, lenf, busy, cap)
        self.record_history = False
        self.keep_raw = False

        self.n_events = 0

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _seed_events(self) -> None:
        for p in self.patients:
            heapq.heappush(self.fel, new_event(p.arrival_time, EventType.ARRIVAL, p))
        for t in self.pool.shift_change_times(self.cfg.horizon):
            heapq.heappush(self.fel, new_event(t, EventType.SHIFT_CHANGE, None))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> "RunResult":
        from .metrics import collect                      # local: avoid cycle
        self._seed_events()
        horizon = self.cfg.horizon
        pop = heapq.heappop
        while self.fel:
            ev = pop(self.fel)
            t = ev[EVT_TIME]
            if t >= horizon:
                # Stop at the horizon.  Work in progress is left unfinished and
                # reported separately -- the paper likewise averages only over
                # consultations that COMPLETED within the simulated week.
                break
            self.now = t
            self.pool.advance_to(t)
            self.n_events += 1
            et = ev[EVT_TYPE]

            if et == EventType.ARRIVAL:
                self._on_arrival(ev[EVT_PAYLOAD])
            elif et == EventType.CONSULT_END:
                self._on_consult_end(ev[EVT_PAYLOAD])
            elif et == EventType.EXAM_DEVICE_FREE:
                self._on_device_free(*ev[EVT_PAYLOAD])
            elif et == EventType.EXAM_RESULTS_READY:
                self._on_results_ready(ev[EVT_PAYLOAD])
            elif et == EventType.SHIFT_CHANGE:
                pass                                       # capacity re-read below

            self._dispatch(t)
            if self.record_history:
                self.queue_history.append(
                    (self.now, len(self.q3), len(self.q4), len(self.qf),
                     self.pool.busy, self.pool.capacity_at(self.now)))

        self.now = horizon
        self.pool.advance_to(horizon)
        return collect(self, keep_raw=self.keep_raw)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_arrival(self, p: Patient) -> None:
        p.stage = Stage.WAIT_INITIAL
        p.queue_entry_time = self.now
        (self.q3 if p.level == C.LEVEL_III else self.q4).append(p)
        self._t(f"ARRIVAL   patient #{p.pid:<5d} Level {p.level}  "
                f"(exams: {len(p.exams)})")

    def _on_consult_end(self, p: Patient) -> None:
        self.pool.release()
        if p.stage == Stage.IN_INITIAL:
            self.busy_initial -= 1
        else:
            self.busy_follow -= 1
        if p.stage == Stage.IN_INITIAL:
            p.initial_end = self.now
            self._t(f"CONSULT-END  #{p.pid:<5d} initial done "
                    f"(waited {p.wait_initial:.1f} min)")
            if p.needs_exam:
                p.stage = Stage.IN_EXAM
                p.exam_start = self.now
                self._start_exam(p, 0)
            else:
                p.stage = Stage.DISCHARGED
        else:                                   # IN_FOLLOW
            p.follow_end = self.now
            p.stage = Stage.DISCHARGED
            self._t(f"CONSULT-END  #{p.pid:<5d} follow-up done "
                    f"(waited {p.wait_follow:.1f} min)")

    # -- diagnostics ----------------------------------------------------
    def _start_exam(self, p: Patient, k: int) -> None:
        """Try to start patient ``p``'s k-th examination (Eq. 4 chain)."""
        order = p.exam_orders[k]
        dev = self.bank[order.modality_index]
        if dev.n_free > 0:
            dev.n_free -= 1
            order.start_time = self.now
            heapq.heappush(self.fel, new_event(
                self.now + order.duration, EventType.EXAM_DEVICE_FREE, (p, k)))
        else:
            dev.queue.append((p, k, self.now))     # incurs rho_j
            self._t(f"EXAM-QUEUE   #{p.pid:<5d} waits for "
                    f"{dev.modality.name}")

    def _on_device_free(self, p: Patient, k: int) -> None:
        order = p.exam_orders[k]
        dev = self.bank[order.modality_index]
        dev.n_free += 1
        dev.n_exams += 1
        dev.busy_minutes += order.duration
        dev.total_duration += order.duration
        order.device_free_time = self.now
        order.ready_time = self.now + order.report_delay   # start + tau + delta
        if order.ready_time > p.exam_ready:
            p.exam_ready = order.ready_time

        # 1) hand the device to the next patient queued for it
        if dev.queue and dev.n_free > 0:
            q, kk, tq = dev.queue.popleft()
            dev.n_free -= 1
            dev.queue_delay_total += self.now - tq
            q.exam_orders[kk].start_time = self.now
            heapq.heappush(self.fel, new_event(
                self.now + q.exam_orders[kk].duration,
                EventType.EXAM_DEVICE_FREE, (q, kk)))

        # 2) advance THIS patient to its next examination (sequential, Eq. 4)
        if k + 1 < len(p.exam_orders):
            self._start_exam(p, k + 1)
        else:
            heapq.heappush(self.fel, new_event(
                p.exam_ready, EventType.EXAM_RESULTS_READY, p))

    def _on_results_ready(self, p: Patient) -> None:
        p.stage = Stage.WAIT_FOLLOW
        p.queue_entry_time = self.now
        self.qf.append(p)
        self._t(f"RESULTS      #{p.pid:<5d} all results in -> follow-up queue")

    # ------------------------------------------------------------------
    # Dispatch -- the single point where the scheduling policy acts
    # ------------------------------------------------------------------
    def _dispatch(self, now: float) -> None:
        R = self.pool.free(now)                  # R^t
        if R <= 0:
            return
        if not (self.q3 or self.q4 or self.qf):
            return
        plan = self.policy.allocate(self, now, R)
        if not plan:
            return
        # The policy inspected the deques without mutating them; remove exactly
        # the patients it selected.  Counting per queue is enough because every
        # policy always selects a prefix of each queue.
        counts = [0, 0, 0]
        for qid, _p in plan:
            counts[qid] += 1
        for qid, n in enumerate(counts):
            dq = (self.q3, self.q4, self.qf)[qid]
            for _ in range(n):
                dq.popleft()
        for qid, p in plan:
            self._begin_service(p, qid, now)

    def _begin_service(self, p: Patient, qid: int, now: float) -> None:
        self.pool.acquire()
        wait = now - p.queue_entry_time
        if qid == QueueId.FOLLOW:
            self.busy_follow += 1
            p.stage = Stage.IN_FOLLOW
            p.wait_follow = wait
            p.follow_start = now
            dur = p.follow_duration
            what = "follow-up"
        else:
            self.busy_initial += 1
            p.stage = Stage.IN_INITIAL
            p.wait_initial = wait
            p.initial_start = now
            dur = p.initial_duration
            what = f"initial L{p.level}"
        heapq.heappush(self.fel, new_event(now + dur, EventType.CONSULT_END, p))
        self._t(f"START     #{p.pid:<5d} {what:<12s} "
                f"wait={wait:6.1f}  svc={dur:5.1f}  "
                f"busy={self.pool.busy}/{self.pool.capacity_at(now)}")

    # ------------------------------------------------------------------
    def _t(self, msg: str) -> None:
        if self.trace is not None:
            self.trace(self.now, msg, self.policy.key)


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------
def simulate(cfg: C.SimConfig, policy: Policy, patients: Sequence[Patient],
             trace=None, record_history: bool = False, keep_raw: bool = False):
    """Run one replication and return its :class:`~src.metrics.RunResult`."""
    sim = Simulation(cfg, policy, patients, trace=trace)
    sim.record_history = record_history
    sim.keep_raw = keep_raw
    res = sim.run()
    if record_history:
        res.queue_history = sim.queue_history
    return res
