"""
test_agent.py
=============
Automated unit tests for the Autonomous Agent (agent.py).
"""

import time
import pytest
from agent import IrrigationAgent
from controller import IrrigationController
from main import ACTION_IRRIGATE, ACTION_STOP, ACTION_WAIT, ACTION_ERROR
from sensors import SensorReading


class TestAutonomousAgent:
    """Test background agent lifecycle, execution cycles, history, and safety."""

    def test_agent_lifecycle_start_stop(self):
        controller = IrrigationController()
        agent = IrrigationAgent(controller=controller, interval_seconds=0.1)

        assert agent.is_running is False
        assert agent.agent_status == "STOPPED"

        # Start agent
        started = agent.start()
        assert started is True
        assert agent.is_running is True
        assert agent.agent_status == "RUNNING"

        # Prevent duplicate workers
        duplicate_start = agent.start()
        assert duplicate_start is False

        # Stop agent
        stopped = agent.stop()
        assert stopped is True
        assert agent.is_running is False
        assert agent.agent_status == "STOPPED"

    def test_irrigation_turned_off_on_agent_stop(self):
        controller = IrrigationController()
        agent = IrrigationAgent(controller=controller, interval_seconds=0.1)

        # Force irrigation ON
        controller.start_irrigation(duration_minutes=10)
        assert controller.is_on is True

        agent.start()
        assert agent.is_running is True

        # Stop agent must force irrigation OFF
        agent.stop()
        assert agent.is_running is False
        assert controller.is_on is False
        assert controller.status_string == "OFF"

    def test_run_cycle_records_decision_and_updates_controller(self):
        controller = IrrigationController()
        agent = IrrigationAgent(controller=controller, interval_seconds=1.0)

        # 1. Supply reading that requires IRRIGATE (Rule 4: dry soil < 30%, rain < 50%)
        dry_reading = SensorReading(
            soil_moisture=20.0,
            temperature=28.0,
            humidity=50.0,
            rainfall_probability=20.0,
            source="test",
        )
        dec = agent.run_cycle(override_reading=dry_reading)
        assert dec.action == ACTION_IRRIGATE
        assert controller.is_on is True
        assert controller.get_status()["duration_minutes"] == 15.0

        # Check history
        history = agent.get_history()
        assert len(history) == 1
        assert history[0]["Action"] == ACTION_IRRIGATE
        assert history[0]["Irrigation"] == "ON"

        # 2. Next cycle with sufficient soil (Rule 2: >= 60%) must STOP irrigation
        wet_reading = SensorReading(
            soil_moisture=65.0,
            temperature=28.0,
            humidity=50.0,
            rainfall_probability=20.0,
            source="test",
        )
        dec2 = agent.run_cycle(override_reading=wet_reading)
        assert dec2.action == ACTION_STOP
        assert controller.is_on is False

        history2 = agent.get_history()
        assert len(history2) == 2
        assert history2[0]["Action"] == ACTION_STOP
        assert history2[0]["Irrigation"] == "OFF"

    def test_safe_handling_of_invalid_readings(self):
        controller = IrrigationController()
        agent = IrrigationAgent(controller=controller, interval_seconds=1.0)

        # Start irrigation first
        controller.start_irrigation(duration_minutes=10)
        assert controller.is_on is True

        # Send invalid reading
        invalid_reading = {
            "soil_moisture": -99.0,
            "temperature": 25.0,
            "humidity": 50.0,
            "rainfall_probability": 20.0,
        }
        dec = agent.run_cycle(override_reading=invalid_reading)
        assert dec.action == ACTION_ERROR
        # Safety guarantee: Sensor errors must shut OFF irrigation!
        assert controller.is_on is False
        assert agent.get_status()["last_error"] is not None

    def test_manual_scenario_evaluation(self):
        controller = IrrigationController()
        agent = IrrigationAgent(controller=controller, interval_seconds=1.0)

        # Evaluate dry soil with rain expected (Rule 3 -> WAIT) without applying to controller
        dec = agent.evaluate_manual_scenario(
            soil_moisture=25.0,
            temperature=30.0,
            humidity=60.0,
            rainfall_probability=70.0,
            apply_to_controller=False,
        )
        assert dec.action == ACTION_WAIT
        assert controller.is_on is False
