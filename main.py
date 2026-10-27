"""
main.py
=======
Decision engine and sensor validation for the Smart Irrigation Autonomous Agent.

Condition-action rules in strict priority order:
1. If humidity > 75% AND rainfall_probability > 60% -> STOP (0 min)
2. If soil_moisture >= 60% -> STOP (0 min)
3. If soil_moisture < 30% AND rainfall_probability >= 50% -> WAIT (0 min)
4. If soil_moisture < 30% AND rainfall_probability < 50% -> IRRIGATE (15 min)
5. If 30% <= soil_moisture <= 45% AND temperature > 32°C AND rainfall_probability < 40% -> IRRIGATE (10 min)
6. Otherwise -> MONITOR (0 min)

All inputs are strictly validated prior to rule evaluation.
Invalid inputs NEVER start irrigation.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Union

from sensors import SensorReading, validate_sensor_data

# Allowed decision actions
ACTION_STOP = "STOP"
ACTION_WAIT = "WAIT"
ACTION_IRRIGATE = "IRRIGATE"
ACTION_MONITOR = "MONITOR"
ACTION_ERROR = "ERROR"


@dataclass
class DecisionResult:
    """Represents the output of the rule-based decision engine."""

    action: str  # 'STOP', 'WAIT', 'IRRIGATE', 'MONITOR', or 'ERROR'
    duration_minutes: int  # 0, 10, or 15
    reason: str  # Human-readable justification
    sensor_readings: Dict[str, Any]  # Snapshot of sensor data evaluated
    timestamp: float = 0.0  # Unix timestamp

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to a dictionary."""
        return asdict(self)


def evaluate_sensor_readings(
    reading_or_dict: Union[SensorReading, Dict[str, Any]],
) -> DecisionResult:
    """
    Validate input sensor values and evaluate condition-action rules in exact priority order.

    Raises:
        ValueError: If sensor data is invalid, non-numeric, or out of physical bounds.

    Returns:
        DecisionResult containing action, duration_minutes, reason, and sensor readings.
    """
    if isinstance(reading_or_dict, SensorReading):
        data = reading_or_dict.to_dict()
    elif isinstance(reading_or_dict, dict):
        data = dict(reading_or_dict)
    else:
        raise ValueError(
            f"Expected SensorReading or dict, received {type(reading_or_dict).__name__}"
        )

    soil_moisture = data.get("soil_moisture")
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    rainfall_probability = data.get("rainfall_probability")

    # Step 1: Input Validation
    is_valid, err_msg = validate_sensor_data(
        soil_moisture=soil_moisture,
        temperature=temperature,
        humidity=humidity,
        rainfall_probability=rainfall_probability,
    )

    if not is_valid:
        raise ValueError(f"Sensor validation failed: {err_msg}")

    # Ensure float precision for comparisons
    sm = float(soil_moisture)
    temp = float(temperature)
    hum = float(humidity)
    rain = float(rainfall_probability)

    snapshot = {
        "soil_moisture": sm,
        "temperature": temp,
        "humidity": hum,
        "rainfall_probability": rain,
        "source": data.get("source", "unknown"),
    }

    # Step 2: Rule Evaluation in Exact Priority Order

    # Rule 1: High humidity and high rainfall probability
    if hum > 75.0 and rain > 60.0:
        return DecisionResult(
            action=ACTION_STOP,
            duration_minutes=0,
            reason=(
                f"Rule 1 triggered: High humidity ({hum:.1f}% > 75%) and high rainfall probability "
                f"({rain:.1f}% > 60%) indicate imminent rain. Stopping/withholding irrigation to conserve water."
            ),
            sensor_readings=snapshot,
        )

    # Rule 2: Sufficient soil moisture
    if sm >= 60.0:
        return DecisionResult(
            action=ACTION_STOP,
            duration_minutes=0,
            reason=(
                f"Rule 2 triggered: Soil moisture ({sm:.1f}%) is sufficient (>= 60%). "
                "No irrigation needed; stopping any active irrigation."
            ),
            sensor_readings=snapshot,
        )

    # Rule 3: Dry soil, but rainfall is likely
    if sm < 30.0 and rain >= 50.0:
        return DecisionResult(
            action=ACTION_WAIT,
            duration_minutes=0,
            reason=(
                f"Rule 3 triggered: Soil moisture is low ({sm:.1f}% < 30%), but rainfall is likely "
                f"({rain:.1f}% >= 50%). Waiting for rain to prevent redundant water usage."
            ),
            sensor_readings=snapshot,
        )

    # Rule 4: Critically dry soil and low rainfall probability
    if sm < 30.0 and rain < 50.0:
        return DecisionResult(
            action=ACTION_IRRIGATE,
            duration_minutes=15,
            reason=(
                f"Rule 4 triggered: Soil is critically dry ({sm:.1f}% < 30%) and rain probability "
                f"is low ({rain:.1f}% < 50%). Activating irrigation for 15 minutes."
            ),
            sensor_readings=snapshot,
        )

    # Rule 5: Moderate soil moisture, high temperature, low rainfall probability
    if 30.0 <= sm <= 45.0 and temp > 32.0 and rain < 40.0:
        return DecisionResult(
            action=ACTION_IRRIGATE,
            duration_minutes=10,
            reason=(
                f"Rule 5 triggered: Soil moisture is moderate ({sm:.1f}% in [30%, 45%]), temperature "
                f"is high ({temp:.1f}°C > 32°C), and rain probability is low ({rain:.1f}% < 40%). "
                "Activating supplementary irrigation for 10 minutes."
            ),
            sensor_readings=snapshot,
        )

    # Rule 6: Default baseline monitoring
    return DecisionResult(
        action=ACTION_MONITOR,
        duration_minutes=0,
        reason=(
            f"Rule 6 triggered: Environmental conditions (Soil: {sm:.1f}%, Temp: {temp:.1f}°C, "
            f"Humidity: {hum:.1f}%, Rain: {rain:.1f}%) are within acceptable parameters. "
            "Continuing routine monitoring."
        ),
        sensor_readings=snapshot,
    )


def safe_evaluate_readings(reading_or_dict: Any) -> DecisionResult:
    """
    Safely evaluate readings without throwing exceptions.
    Returns an ACTION_ERROR DecisionResult if input is invalid.
    """
    try:
        return evaluate_sensor_readings(reading_or_dict)
    except Exception as exc:
        fallback_data = (
            reading_or_dict.to_dict()
            if hasattr(reading_or_dict, "to_dict")
            else dict(reading_or_dict)
            if isinstance(reading_or_dict, dict)
            else {"raw": str(reading_or_dict)}
        )
        return DecisionResult(
            action=ACTION_ERROR,
            duration_minutes=0,
            reason=f"Validation error: {exc}",
            sensor_readings=fallback_data,
        )


if __name__ == "__main__":
    print("--- Smart Irrigation Decision Engine Verification ---")
    test_scenarios = [
        {"name": "Rule 1 (High Hum & Rain)", "data": {"soil_moisture": 25.0, "temperature": 28.0, "humidity": 80.0, "rainfall_probability": 65.0}},
        {"name": "Rule 2 (Sufficient Moisture)", "data": {"soil_moisture": 65.0, "temperature": 30.0, "humidity": 50.0, "rainfall_probability": 10.0}},
        {"name": "Rule 3 (Dry soil, Rain Expected)", "data": {"soil_moisture": 22.0, "temperature": 29.0, "humidity": 60.0, "rainfall_probability": 55.0}},
        {"name": "Rule 4 (Dry soil, Low Rain)", "data": {"soil_moisture": 20.0, "temperature": 28.0, "humidity": 50.0, "rainfall_probability": 20.0}},
        {"name": "Rule 5 (Moderate Soil, High Heat)", "data": {"soil_moisture": 35.0, "temperature": 35.0, "humidity": 40.0, "rainfall_probability": 15.0}},
        {"name": "Rule 6 (Normal Conditions)", "data": {"soil_moisture": 50.0, "temperature": 24.0, "humidity": 55.0, "rainfall_probability": 20.0}},
        {"name": "Invalid Input (Soil Moisture > 100)", "data": {"soil_moisture": 110.0, "temperature": 24.0, "humidity": 55.0, "rainfall_probability": 20.0}},
    ]

    for scenario in test_scenarios:
        res = safe_evaluate_readings(scenario["data"])
        print(f"[{scenario['name']}] -> Action: {res.action}, Duration: {res.duration_minutes}m")
        print(f"  Reason: {res.reason}\n")
