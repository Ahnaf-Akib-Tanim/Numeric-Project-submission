"""
entities.py -- ENTITY DEFINITION MODULE  (Figure 2, box 1 of the base paper).

Defines the data structures that flow through the simulation:

    Patient   -- one ED visit, carrying every pre-drawn random attribute
    ExamOrder -- one (patient, modality) diagnostic task
    Event     -- one entry of the future-event list
    Stage     -- where in the care pathway a patient currently is

Design note (important for WP5 / Common Random Numbers):
    A ``Patient`` is created with ALL of its random attributes already drawn --
    arrival time, triage level, both consultation durations, whether it needs
    examinations and which ones.  The engine never draws a random number while
    running.  Consequently two runs of two DIFFERENT scheduling policies over
    the same patient stream differ *only* in the scheduling decisions, which is
    exactly the variance-reduction property CRN is supposed to give.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Tuple


class Stage(IntEnum):
    """Where the patient is in the pathway (Figure 1 of the paper)."""
    ARRIVING = 0        # not yet in the system
    WAIT_INITIAL = 1    # in W_init,3 or W_init,4
    IN_INITIAL = 2      # being consulted (first consultation)
    IN_EXAM = 3         # queueing for / undergoing diagnostics
    WAIT_FOLLOW = 4     # in W_follow
    IN_FOLLOW = 5       # being consulted (follow-up)
    DISCHARGED = 6


class EventType(IntEnum):
    """Future-event-list entry kinds.

    The integer values double as the tie-break priority when two events share
    a timestamp: lower value fires first.  SHIFT_CHANGE must precede everything
    so that a physician count change is visible to any dispatch at that instant;
    DISPATCH must fire last so it sees a fully-updated system state.
    """
    SHIFT_CHANGE = 0
    ARRIVAL = 1
    CONSULT_END = 2
    EXAM_DEVICE_FREE = 3
    EXAM_RESULTS_READY = 4
    DISPATCH = 5


# ---------------------------------------------------------------------------
# Future-event-list entries
#
# An event is a plain 4-tuple  (time, etype, seq, payload)  rather than a class.
# heapq compares items element-by-element, and tuple comparison runs entirely in
# C; using a dataclass with ``order=True`` made Python-level ``__lt__`` calls
# ~22% of total runtime in profiling.  ``seq`` is a monotone counter that makes
# the ordering total (FIFO among identical time+type pairs), so a replication is
# reproducible bit-for-bit.
# ---------------------------------------------------------------------------
EVT_TIME, EVT_TYPE, EVT_SEQ, EVT_PAYLOAD = 0, 1, 2, 3

_seq_counter = itertools.count()


def new_event(time: float, etype: int, payload=None) -> Tuple[float, int, int, object]:
    """Build one future-event-list entry."""
    return (time, int(etype), next(_seq_counter), payload)


@dataclass(slots=True)
class ExamOrder:
    """A single diagnostic task for one patient on one modality."""
    modality_index: int      # index into cfg.modalities
    duration: float          # tau_j
    report_delay: float      # delta_j
    start_time: float = -1.0     # t^start_{i,j,k}  (Eq. 4)
    device_free_time: float = -1.0
    ready_time: float = -1.0     # start + tau_j + delta_j


@dataclass(slots=True)
class Patient:
    """One ED visit.  All random attributes are drawn *before* the run starts."""

    pid: int
    arrival_time: float          # t of A^t_arrive
    level: int                   # 3 or 4
    initial_duration: float      # T_i^(1)
    follow_duration: float       # T_i^(2)  (only used if needs_exam)
    needs_exam: bool
    exams: Tuple[int, ...]       # indices of required modalities, ordered by
                                 # DESCENDING report delay  [paper Sec 2.1.3]

    # ---- state filled in during the run -------------------------------------
    stage: int = Stage.ARRIVING
    queue_entry_time: float = -1.0   # when the current wait started
    initial_start: float = -1.0
    initial_end: float = -1.0
    exam_start: float = -1.0
    exam_ready: float = -1.0         # t_i^exam  (Eq. 4)
    follow_start: float = -1.0
    follow_end: float = -1.0
    wait_initial: float = -1.0       # w_i for the initial consultation
    wait_follow: float = -1.0        # w_i for the follow-up consultation
    exam_orders: List[ExamOrder] = field(default_factory=list)

    # ---- helpers ------------------------------------------------------------
    def waiting_time(self, now: float) -> float:
        """Elapsed wait in the *current* queue -- w_i(t) of Eq. 14."""
        return now - self.queue_entry_time if self.queue_entry_time >= 0 else 0.0

    @property
    def total_wait(self) -> float:
        """Sum of both waits; the per-patient quantity behind Eq. 26."""
        w = self.wait_initial if self.wait_initial >= 0 else 0.0
        if self.wait_follow >= 0:
            w += self.wait_follow
        return w

    @property
    def completed_initial(self) -> bool:
        return self.initial_end >= 0

    @property
    def completed_follow(self) -> bool:
        return self.follow_end >= 0


# ---------------------------------------------------------------------------
# Queue identifiers.  The paper's three competing queues, Sec 2.1.4.
# ---------------------------------------------------------------------------
class QueueId(IntEnum):
    INIT_3 = 0     # W^t_init,3
    INIT_4 = 1     # W^t_init,4
    FOLLOW = 2     # W^t_follow


QUEUE_NAMES = {QueueId.INIT_3: "init_L3", QueueId.INIT_4: "init_L4",
               QueueId.FOLLOW: "follow"}
