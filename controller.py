"""
controller.py
=============
Simulated Irrigation Controller for the Smart Irrigation Autonomous Agent.

Provides thread-safe control for:
- Activating irrigation with a validated duration (max 15 minutes).
- Tracking real-time countdown using monotonic time.
- Automatic shutdown when the duration expires.
- Manual emergency / routine stop operations.
- Protection against overlapping irrigation sessions.
- Clean shutdown and countdown reset.

NOTE: This is a software simulation. No physical relays or valves are operated.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, Optional, Tuple


class IrrigationController:
    """Thread-safe controller simulating physical irrigation hardware."""

    MAX_DURATION_MINUTES: float = 15.0  # Strict safety maximum per session

    def __init__(self, time_scale: float = 1.0) -> None:
        """
        Initialize the irrigation controller.

        Args:
            time_scale: Speed multiplier for simulation / testing (default 1.0).
                        A time_scale of 60.0 means 1 minute passes in 1 second.
        """
        self._lock = threading.RLock()
        self._is_on: bool = False
        self._duration_minutes: float = 0.0
        self._duration_seconds: float = 0.0
        self._start_monotonic: float = 0.0
        self._end_monotonic: float = 0.0
        self._last_reason: str = "System initialized (OFF)"
        self._time_scale: float = max(0.001, float(time_scale))

    @property
    def is_on(self) -> bool:
        """Return True if irrigation is currently running."""
        with self._lock:
            self._check_auto_expiration()
            return self._is_on

    @property
    def status_string(self) -> str:
        """Return 'ON' or 'OFF'."""
        return "ON" if self.is_on else "OFF"

    def _check_auto_expiration(self) -> None:
        """Check if active irrigation session has reached its scheduled end time."""
        if not self._is_on:
            return

        now = time.monotonic()
        if now >= self._end_monotonic:
            self._is_on = False
            self._last_reason = (
                f"Irrigation completed automatically ({self._duration_minutes:.1f} min elapsed)."
            )
            self._duration_minutes = 0.0
            self._duration_seconds = 0.0
            self._start_monotonic = 0.0
            self._end_monotonic = 0.0

    def start_irrigation(
        self,
        duration_minutes: float,
        reason: str = "",
        duration_seconds: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Safely start an irrigation session.

        Args:
            duration_minutes: Irrigation duration in minutes (0 < duration <= 15).
            reason: Optional explanation for starting.
            duration_seconds: Optional explicit duration in seconds (for micro-tests).

        Raises:
            ValueError: If duration is non-numeric, <= 0, or exceeds MAX_DURATION_MINUTES.

        Returns:
            (success, message): Boolean indicating whether irrigation was started, and details.
        """
        # Validate duration inputs
        if duration_minutes is None and duration_seconds is None:
            raise ValueError("Irrigation duration must be specified.")

        if duration_seconds is not None:
            if not isinstance(duration_seconds, (int, float)) or isinstance(duration_seconds, bool):
                raise ValueError("duration_seconds must be a numeric value.")
            if duration_seconds <= 0:
                raise ValueError("Irrigation duration must be greater than 0.")
            effective_seconds = float(duration_seconds)
            effective_minutes = effective_seconds / 60.0
        else:
            if not isinstance(duration_minutes, (int, float)) or isinstance(duration_minutes, bool):
                raise ValueError("duration_minutes must be a numeric value.")
            if math.isnan(duration_minutes) or math.isinf(duration_minutes):
                raise ValueError("duration_minutes must be a finite number.")
            if duration_minutes <= 0:
                raise ValueError("Irrigation duration must be greater than 0 minutes.")
            if duration_minutes > self.MAX_DURATION_MINUTES:
                raise ValueError(
                    f"Requested duration ({duration_minutes} min) exceeds maximum permitted limit "
                    f"of {self.MAX_DURATION_MINUTES} minutes."
                )

            effective_minutes = float(duration_minutes)
            effective_seconds = (effective_minutes * 60.0) / self._time_scale

        with self._lock:
            self._check_auto_expiration()

            # Overlapping session prevention
            if self._is_on:
                remaining = max(0.0, self._end_monotonic - time.monotonic())
                return (
                    False,
                    f"Irrigation is already active ({remaining:.1f}s remaining). Overlapping sessions are prevented.",
                )

            # Activate irrigation
            now = time.monotonic()
            self._is_on = True
            self._duration_minutes = effective_minutes
            self._duration_seconds = effective_seconds
            self._start_monotonic = now
            self._end_monotonic = now + effective_seconds
            self._last_reason = (
                reason
                or f"Started irrigation for {effective_minutes:.1f} min ({effective_seconds:.1f}s real time)."
            )
            return True, f"Irrigation started successfully for {effective_minutes:.1f} min."

    def stop_irrigation(self, reason: str = "Manual stop") -> Tuple[bool, str]:
        """
        Safely stop irrigation immediately and reset countdown.
        Idempotent operation: safe to call even if already stopped.
        """
        with self._lock:
            was_on = self._is_on
            self._is_on = False
            self._duration_minutes = 0.0
            self._duration_seconds = 0.0
            self._start_monotonic = 0.0
            self._end_monotonic = 0.0
            self._last_reason = reason

            if was_on:
                return True, f"Irrigation stopped: {reason}"
            return True, f"Irrigation is already OFF: {reason}"

    def get_remaining_seconds(self) -> float:
        """Return the number of remaining seconds in the current irrigation session."""
        with self._lock:
            self._check_auto_expiration()
            if not self._is_on:
                return 0.0
            return max(0.0, self._end_monotonic - time.monotonic())

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of current controller state."""
        with self._lock:
            self._check_auto_expiration()
            remaining_sec = self.get_remaining_seconds()

            if self._is_on and remaining_sec > 0:
                mins = int(remaining_sec // 60)
                secs = int(remaining_sec % 60)
                formatted = f"{mins}m {secs:02d}s"
            else:
                formatted = "0m 00s"

            return {
                "is_on": self._is_on,
                "status": "ON" if self._is_on else "OFF",
                "remaining_seconds": round(remaining_sec, 1),
                "remaining_formatted": formatted,
                "duration_minutes": round(self._duration_minutes, 1),
                "last_reason": self._last_reason,
            }
