"""
agent.py
========
Autonomous Monitoring Agent for the Smart Irrigation System.

Responsibilities:
- Periodic environmental sensor reading retrieval.
- Rule-based decision evaluation using main.py.
- Execution of decisions against the simulated irrigation controller.
- Thread-safe shared state management and bounded history tracking.
- Independent background monitoring thread with clean, prompt start/stop lifecycle.
- Fail-safe shutdown ensuring irrigation is turned OFF when the agent stops.
"""

from __future__ import annotations

import collections
import datetime
import threading
import time
from typing import Any, Dict, List, Optional, Union

from controller import IrrigationController
from main import (
    ACTION_ERROR,
    ACTION_IRRIGATE,
    ACTION_MONITOR,
    ACTION_STOP,
    ACTION_WAIT,
    DecisionResult,
    evaluate_sensor_readings,
    safe_evaluate_readings,
)
from sensors import SensorReading, generate_sensor_reading


class IrrigationAgent:
    """
    Autonomous agent coordinating simulated sensors, decision logic,
    and the irrigation controller in a background thread.
    """

    MAX_HISTORY_ENTRIES: int = 500

    def __init__(
        self,
        controller: Optional[IrrigationController] = None,
        interval_seconds: float = 5.0,
    ) -> None:
        """
        Initialize the autonomous irrigation agent.

        Args:
            controller: IrrigationController instance (created if not provided).
            interval_seconds: Monitoring interval in seconds (default 5.0s).
        """
        self.controller = controller or IrrigationController()
        self.interval_seconds = max(0.5, float(interval_seconds))

        self._lock = threading.RLock()
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Shared state
        self._latest_reading: Optional[SensorReading] = None
        self._latest_decision: Optional[DecisionResult] = None
        self._last_error: Optional[str] = None
        self._history: collections.deque[Dict[str, Any]] = collections.deque(
            maxlen=self.MAX_HISTORY_ENTRIES
        )

        # Baseline reading seed
        self._latest_reading = generate_sensor_reading(previous=None, is_irrigating=False)

    @property
    def is_running(self) -> bool:
        """Check if the agent monitoring thread is active."""
        with self._lock:
            return self._is_running

    @property
    def agent_status(self) -> str:
        """Return 'RUNNING' or 'STOPPED'."""
        return "RUNNING" if self.is_running else "STOPPED"

    def start(self) -> bool:
        """
        Start the autonomous background monitoring thread.
        Idempotent: prevents creating duplicate monitoring threads.
        """
        with self._lock:
            if self._is_running:
                return False  # Already running

            self._is_running = True
            self._stop_event.clear()
            self._last_error = None

            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="SmartIrrigationMonitoringThread",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> bool:
        """
        Stop the monitoring agent and safely turn irrigation OFF.
        Idempotent: safe to call if already stopped.
        """
        with self._lock:
            if not self._is_running:
                # Always ensure irrigation is OFF on stop request
                self.controller.stop_irrigation(reason="Agent stopped")
                return False

            self._is_running = False
            self._stop_event.set()

        # Wait for thread to terminate promptly outside lock to prevent deadlocks
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        with self._lock:
            self._thread = None
            # Safety guarantee: Turn simulated irrigation OFF when stopped
            self.controller.stop_irrigation(reason="Agent monitoring stopped")

        return True

    def _monitor_loop(self) -> None:
        """Continuous background monitoring execution loop."""
        while not self._stop_event.is_set():
            try:
                self.run_cycle(source="simulated")
            except Exception as exc:
                with self._lock:
                    self._last_error = f"Error in monitoring cycle: {exc}"

            # Wait for the next cycle or early stop notification
            if self._stop_event.wait(timeout=self.interval_seconds):
                break

    def run_cycle(
        self,
        override_reading: Optional[Union[SensorReading, Dict[str, Any]]] = None,
        source: str = "simulated",
    ) -> DecisionResult:
        """
        Execute a single monitoring cycle:
        1. Obtain sensor reading (auto-generated or override).
        2. Evaluate rules via decision engine.
        3. Apply decision to the irrigation controller.
        4. Record to bounded history.
        """
        with self._lock:
            # 1. Obtain reading
            if override_reading is not None:
                if isinstance(override_reading, SensorReading):
                    reading = override_reading
                else:
                    reading = SensorReading.from_dict(override_reading)
            else:
                is_irrigating = self.controller.is_on
                reading = generate_sensor_reading(
                    previous=self._latest_reading,
                    is_irrigating=is_irrigating,
                    source=source,
                )

            self._latest_reading = reading

            # 2. Evaluate rules
            decision = safe_evaluate_readings(reading)
            self._latest_decision = decision

            # 3. Apply decision to Controller
            if decision.action == ACTION_IRRIGATE:
                if not self.controller.is_on:
                    self.controller.start_irrigation(
                        duration_minutes=decision.duration_minutes,
                        reason=decision.reason,
                    )
            elif decision.action in (ACTION_STOP, ACTION_WAIT):
                if self.controller.is_on:
                    self.controller.stop_irrigation(reason=decision.reason)
            elif decision.action == ACTION_ERROR:
                # If sensor error occurs, prioritize safety: shut down irrigation
                if self.controller.is_on:
                    self.controller.stop_irrigation(
                        reason=f"Safety shutdown due to sensor error: {decision.reason}"
                    )
                self._last_error = decision.reason
            # ACTION_MONITOR: No change, let active irrigation finish if running

            # 4. Record to history
            controller_status = self.controller.get_status()
            ts_str = datetime.datetime.fromtimestamp(
                reading.timestamp
            ).strftime("%Y-%m-%d %H:%M:%S")

            history_entry = {
                "Timestamp": ts_str,
                "Soil Moisture (%)": f"{reading.soil_moisture:.1f}%",
                "Temperature (°C)": f"{reading.temperature:.1f}°C",
                "Humidity (%)": f"{reading.humidity:.1f}%",
                "Rainfall Prob (%)": f"{reading.rainfall_probability:.1f}%",
                "Action": decision.action,
                "Duration": f"{decision.duration_minutes}m",
                "Irrigation": controller_status["status"],
                "Remaining": controller_status["remaining_formatted"],
                "Source": reading.source,
                "Reason": decision.reason,
            }
            self._history.appendleft(history_entry)

            return decision

    def evaluate_manual_scenario(
        self,
        soil_moisture: float,
        temperature: float,
        humidity: float,
        rainfall_probability: float,
        apply_to_controller: bool = False,
    ) -> DecisionResult:
        """
        Evaluate a manual sensor scenario.
        Optionally apply the resulting action to the controller.
        """
        reading = SensorReading(
            soil_moisture=soil_moisture,
            temperature=temperature,
            humidity=humidity,
            rainfall_probability=rainfall_probability,
            timestamp=time.time(),
            source="manual",
        )

        if apply_to_controller:
            return self.run_cycle(override_reading=reading, source="manual")

        # Just evaluate without modifying controller
        decision = safe_evaluate_readings(reading)
        with self._lock:
            self._latest_reading = reading
            self._latest_decision = decision
            if decision.action == ACTION_ERROR:
                self._last_error = decision.reason
        return decision

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive status for UI dashboard consumption."""
        with self._lock:
            controller_status = self.controller.get_status()
            reading_dict = self._latest_reading.to_dict() if self._latest_reading else {}
            decision_dict = self._latest_decision.to_dict() if self._latest_decision else {}

            return {
                "agent_status": self.agent_status,
                "controller_status": controller_status["status"],
                "is_irrigating": controller_status["is_on"],
                "remaining_time": controller_status["remaining_formatted"],
                "remaining_seconds": controller_status["remaining_seconds"],
                "latest_reading": reading_dict,
                "latest_decision": decision_dict,
                "last_error": self._last_error,
                "history_count": len(self._history),
            }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return a copy of recent history entries as a list of dicts."""
        with self._lock:
            entries = list(self._history)
            return entries[:limit]
