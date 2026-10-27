"""
test_controller.py
==================
Automated unit tests for the Irrigation Controller (controller.py).
"""

import time
import pytest
from controller import IrrigationController


class TestIrrigationController:
    """Test controller states, durations, timer, and safety protections."""

    def test_initial_state_is_off(self):
        controller = IrrigationController()
        assert controller.is_on is False
        assert controller.status_string == "OFF"
        assert controller.get_remaining_seconds() == 0.0

    def test_start_irrigation_valid_duration(self):
        controller = IrrigationController()
        success, msg = controller.start_irrigation(duration_minutes=10, reason="Test start")
        assert success is True
        assert controller.is_on is True
        assert controller.status_string == "ON"
        assert controller.get_remaining_seconds() > 0.0
        assert "started successfully" in msg

    def test_reject_zero_or_negative_duration(self):
        controller = IrrigationController()
        with pytest.raises(ValueError, match="greater than 0"):
            controller.start_irrigation(duration_minutes=0)

        with pytest.raises(ValueError, match="greater than 0"):
            controller.start_irrigation(duration_minutes=-5)

    def test_reject_over_limit_duration(self):
        controller = IrrigationController()
        with pytest.raises(ValueError, match="exceeds maximum permitted limit"):
            controller.start_irrigation(duration_minutes=15.1)

        with pytest.raises(ValueError, match="exceeds maximum permitted limit"):
            controller.start_irrigation(duration_minutes=30)

    def test_reject_non_numeric_duration(self):
        controller = IrrigationController()
        with pytest.raises(ValueError, match="numeric"):
            controller.start_irrigation(duration_minutes="ten")  # type: ignore

        with pytest.raises(ValueError, match="numeric"):
            controller.start_irrigation(duration_minutes=True)  # type: ignore

    def test_prevent_overlapping_sessions(self):
        controller = IrrigationController()
        ok1, msg1 = controller.start_irrigation(duration_minutes=10)
        assert ok1 is True
        assert controller.is_on is True

        # Second start while already ON must be rejected
        ok2, msg2 = controller.start_irrigation(duration_minutes=5)
        assert ok2 is False
        assert "already active" in msg2
        assert "Overlapping sessions are prevented" in msg2

    def test_manual_stop_resets_countdown(self):
        controller = IrrigationController()
        controller.start_irrigation(duration_minutes=10)
        assert controller.is_on is True
        assert controller.get_remaining_seconds() > 0

        ok, msg = controller.stop_irrigation(reason="Manual intervention")
        assert ok is True
        assert controller.is_on is False
        assert controller.status_string == "OFF"
        assert controller.get_remaining_seconds() == 0.0
        assert "Manual intervention" in msg

    def test_automatic_shutdown_after_duration_expires(self):
        """Test automatic expiration using a short duration."""
        controller = IrrigationController()
        # Start with 0.15 seconds duration
        ok, msg = controller.start_irrigation(duration_minutes=1, duration_seconds=0.15)
        assert ok is True
        assert controller.is_on is True

        # Wait for duration to elapse
        time.sleep(0.2)

        # Calling status or property triggers auto expiration check
        assert controller.is_on is False
        assert controller.status_string == "OFF"
        assert controller.get_remaining_seconds() == 0.0
        assert "completed automatically" in controller.get_status()["last_reason"]

    def test_stop_when_already_off_is_safe_idempotent(self):
        controller = IrrigationController()
        assert controller.is_on is False
        ok, msg = controller.stop_irrigation()
        assert ok is True
        assert "already OFF" in msg
