"""Conservative GPS distance; never interpolate missing collection intervals."""

from app.tracking import distance_m

GAP_SECONDS = 600
MAX_ACCURACY_M = 100
MAX_SPEED_KMH = 160


class DistanceCounter:
    def __init__(self):
        self.previous = self.anchor = self.first = self.last = None
        self.session = None
        self.total_m = 0.0
        self.samples = self.intervals = 0
        self.gaps = self.transfers = self.inaccurate = 0
        self.jumps = self.invalid_time = 0

    def add(self, point):
        self.samples += 1
        if self.session is not None and point["session_id"] != self.session:
            self.transfers += 1
            self.previous = self.anchor = None
        self.session = point["session_id"]
        if point["accuracy_m"] > MAX_ACCURACY_M:
            self.inaccurate += 1
            self.previous = self.anchor = None
            return
        if self.previous:
            seconds = (
                point["captured_at"] - self.previous["captured_at"]
            ).total_seconds()
            distance = distance_m(
                self.previous["latitude"],
                self.previous["longitude"],
                point["latitude"],
                point["longitude"],
            )
            uncertainty = max(15, self.previous["accuracy_m"] + point["accuracy_m"])
            if seconds <= 0:
                if distance > uncertainty:
                    self.invalid_time += 1
                return
            if seconds > GAP_SECONDS:
                self.gaps += 1
                self.anchor = None
            elif max(0, distance - uncertainty) * 3.6 / seconds > MAX_SPEED_KMH:
                self.jumps += 1
                # Keep the last plausible point so one spike cannot inflate its return.
                return
            else:
                self.intervals += 1
                movement = distance_m(
                    self.anchor["latitude"],
                    self.anchor["longitude"],
                    point["latitude"],
                    point["longitude"],
                )
                # Keep the distance anchor until movement exceeds GPS uncertainty.
                if movement > max(15, self.anchor["accuracy_m"] + point["accuracy_m"]):
                    self.total_m += movement
                    self.anchor = point
        self.anchor = self.anchor or point
        self.previous = self.last = point
        self.first = self.first or point

    def summary(self, started_at=None, ended_at=None, cutoff=None):
        boundary_gaps = int(
            bool(
                self.first
                and started_at
                and (self.first["captured_at"] - started_at).total_seconds()
                > GAP_SECONDS
            )
        )
        boundary_gaps += int(
            bool(
                self.last
                and ended_at
                and (ended_at - self.last["captured_at"]).total_seconds() > GAP_SECONDS
            )
        )
        retention_limited = bool(cutoff and started_at and started_at < cutoff)
        return {
            "distance_m": round(self.total_m) if self.intervals else None,
            "samples": self.samples,
            "valid_intervals": self.intervals,
            "gaps": self.gaps + boundary_gaps,
            "session_breaks": self.transfers,
            "rejected_accuracy": self.inaccurate,
            "rejected_jumps": self.jumps,
            "invalid_timestamps": self.invalid_time,
            "retention_limited": retention_limited,
            "partial": bool(
                not self.intervals
                or self.gaps
                or boundary_gaps
                or self.transfers
                or self.inaccurate
                or self.jumps
                or self.invalid_time
                or retention_limited
            ),
        }
