"""
resources.py -- RESOURCE SCHEDULING MODULE  (Figure 2, box 3 of the paper).

Two resource types:

    PhysicianPool -- R^t doctors, a *time-varying* capacity driven by the three
                     daily shifts.  Non-preemptive: "Once a physician begins
                     service, the service process will not be interrupted"
                     [paper, after Eq. 10].  So when a shift shrinks (22:00,
                     5 -> 3 doctors) any over-count simply works off its
                     current patient and no new work starts until the busy
                     count falls back below capacity.

    DeviceBank    -- J diagnostic modalities, each with C_j parallel units and
                     a FIFO queue.  Waiting for a busy device is the rho_j term
                     of Eq. (4).
"""
from __future__ import annotations

from collections import deque
from typing import Deque, List, Sequence

from . import config as C


# ---------------------------------------------------------------------------
# Physicians
# ---------------------------------------------------------------------------
class PhysicianPool:
    """Time-varying server pool with non-preemptive service."""

    __slots__ = ("_by_hour", "busy", "_last_t", "busy_minutes",
                 "capacity_minutes", "_cap_now", "n_consults")

    def __init__(self, shifts: Sequence[C.Shift]):
        # Flatten the (possibly midnight-wrapping) shift list into a 24-slot
        # lookup: hour -> number of physicians on duty.
        self._by_hour: List[int] = [0] * 24
        for s in shifts:
            h = s.start_hour
            length = (s.end_hour - s.start_hour) % 24 or 24
            for _ in range(length):
                self._by_hour[h % 24] = s.physicians
                h += 1
        if 0 in self._by_hour:
            raise ValueError("shift definition leaves some hour unstaffed")

        self.busy = 0
        self._last_t = 0.0
        self.busy_minutes = 0.0        # integral of busy(t) dt
        self.capacity_minutes = 0.0    # integral of R(t) dt
        self._cap_now = self._by_hour[0]
        self.n_consults = 0            # N^{t,s}_served, Eq. 29

    # -- capacity -----------------------------------------------------------
    def capacity_at(self, t: float) -> int:
        """R^t -- physicians rostered at simulation time ``t``."""
        h = int((t % C.MINUTES_PER_DAY) // C.MINUTES_PER_HOUR)
        return self._by_hour[h]

    def shift_change_times(self, horizon: float) -> List[float]:
        """All epochs in [0, horizon) at which R(t) changes value."""
        out: List[float] = []
        for day in range(int(horizon // C.MINUTES_PER_DAY) + 1):
            for h in range(24):
                if self._by_hour[h] != self._by_hour[(h - 1) % 24]:
                    t = day * C.MINUTES_PER_DAY + h * C.MINUTES_PER_HOUR
                    if 0.0 < t < horizon:
                        out.append(float(t))
        return sorted(out)

    # -- time-weighted accounting -------------------------------------------
    def advance_to(self, t: float) -> None:
        """Accrue busy-time and capacity-time integrals up to ``t``.

        Called on EVERY event so that utilisation is a proper time average
        (paper: "the ratio of busy time to total available time"), not an
        event-count average.
        """
        dt = t - self._last_t
        if dt > 0.0:
            self.busy_minutes += self.busy * dt
            self.capacity_minutes += self._cap_now * dt
            self._last_t = t
        self._cap_now = self.capacity_at(t)

    # -- allocation ---------------------------------------------------------
    def free(self, t: float) -> int:
        """Number of physicians that may start a NEW consultation right now."""
        return max(0, self.capacity_at(t) - self.busy)

    def acquire(self) -> None:
        self.busy += 1

    def release(self) -> None:
        self.busy -= 1
        self.n_consults += 1

    @property
    def utilisation(self) -> float:
        return self.busy_minutes / self.capacity_minutes if self.capacity_minutes else 0.0


# ---------------------------------------------------------------------------
# Diagnostic devices
# ---------------------------------------------------------------------------
class Device:
    """One diagnostic modality j with C_j identical units and a FIFO queue."""

    __slots__ = ("modality", "index", "n_free", "queue", "busy_minutes",
                 "n_exams", "total_duration", "queue_delay_total")

    def __init__(self, index: int, modality: C.Modality):
        self.index = index
        self.modality = modality
        self.n_free = modality.capacity
        self.queue: Deque = deque()        # of (patient, order_index)
        self.busy_minutes = 0.0
        self.n_exams = 0
        self.total_duration = 0.0
        self.queue_delay_total = 0.0       # sum of rho_j actually incurred

    def utilisation(self, horizon: float) -> float:
        """U_j of Eq. (30): busy device-minutes / available device-minutes."""
        denom = horizon * self.modality.capacity
        return self.busy_minutes / denom if denom else 0.0


class DeviceBank:
    """All J modalities."""

    __slots__ = ("devices",)

    def __init__(self, modalities: Sequence[C.Modality]):
        self.devices: List[Device] = [Device(i, m) for i, m in enumerate(modalities)]

    def __getitem__(self, j: int) -> Device:
        return self.devices[j]

    def __iter__(self):
        return iter(self.devices)

    def summary(self, horizon: float):
        return {
            d.modality.name: {
                "n_exams": d.n_exams,
                "mean_duration": (d.total_duration / d.n_exams) if d.n_exams else 0.0,
                "total_duration": d.total_duration,
                "available_minutes": horizon * d.modality.capacity,
                "utilisation": d.utilisation(horizon),
                "mean_queue_delay": (d.queue_delay_total / d.n_exams) if d.n_exams else 0.0,
            }
            for d in self.devices
        }
