"""
test_decisions.py
=================
Automated unit tests for the Rule-Based Decision Engine (main.py).
"""

import pytest
from main import (
    ACTION_ERROR,
    ACTION_IRRIGATE,
    ACTION_MONITOR,
    ACTION_STOP,
    ACTION_WAIT,
    evaluate_sensor_readings,
    safe_evaluate_readings,
)
from sensors import SensorReading, validate_sensor_data


class TestDecisionRules:
    """Test standard condition-action rules and required scenarios."""

    def test_rule_1_high_humidity_and_high_rainfall(self):
        """Rule 1: Humidity > 75% AND rainfall_probability > 60% -> STOP (0 min)."""
        reading = {
            "soil_moisture": 20.0,  # Even with dry soil
            "temperature": 35.0,
            "humidity": 76.0,
            "rainfall_probability": 61.0,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_STOP
        assert res.duration_minutes == 0
        assert "Rule 1" in res.reason

    def test_rule_2_sufficient_soil_moisture(self):
        """Rule 2: Soil moisture >= 60% -> STOP (0 min)."""
        reading = {
            "soil_moisture": 60.0,
            "temperature": 30.0,
            "humidity": 40.0,
            "rainfall_probability": 10.0,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_STOP
        assert res.duration_minutes == 0
        assert "Rule 2" in res.reason

        # Upper bound test
        reading["soil_moisture"] = 95.0
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_STOP
        assert res.duration_minutes == 0

    def test_rule_3_dry_soil_high_rainfall_probability(self):
        """Rule 3: Soil moisture < 30% AND rainfall_probability >= 50% -> WAIT (0 min)."""
        reading = {
            "soil_moisture": 25.0,
            "temperature": 28.0,
            "humidity": 50.0,
            "rainfall_probability": 50.0,  # Boundary test: exactly 50%
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_WAIT
        assert res.duration_minutes == 0
        assert "Rule 3" in res.reason

    def test_rule_4_dry_soil_low_rainfall_probability(self):
        """Rule 4: Soil moisture < 30% AND rainfall_probability < 50% -> IRRIGATE (15 min)."""
        reading = {
            "soil_moisture": 15.0,
            "temperature": 25.0,
            "humidity": 45.0,
            "rainfall_probability": 49.9,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_IRRIGATE
        assert res.duration_minutes == 15
        assert "Rule 4" in res.reason

    def test_rule_5_moderate_moisture_high_temp_low_rain(self):
        """
        Rule 5: 30% <= soil_moisture <= 45% AND temperature > 32°C AND
        rainfall_probability < 40% -> IRRIGATE (10 min).
        """
        reading = {
            "soil_moisture": 35.0,
            "temperature": 32.5,
            "humidity": 50.0,
            "rainfall_probability": 30.0,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_IRRIGATE
        assert res.duration_minutes == 10
        assert "Rule 5" in res.reason

        # Boundaries of Rule 5: 30% and 45% inclusive
        reading["soil_moisture"] = 30.0
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_IRRIGATE
        assert res.duration_minutes == 10

        reading["soil_moisture"] = 45.0
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_IRRIGATE
        assert res.duration_minutes == 10

    def test_rule_6_routine_monitoring(self):
        """Rule 6: Conditions not matching prior rules -> MONITOR (0 min)."""
        reading = {
            "soil_moisture": 50.0,
            "temperature": 25.0,
            "humidity": 55.0,
            "rainfall_probability": 20.0,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_MONITOR
        assert res.duration_minutes == 0
        assert "Rule 6" in res.reason

        # Moderate soil (35%), but temperature not > 32°C
        reading = {
            "soil_moisture": 35.0,
            "temperature": 30.0,
            "humidity": 55.0,
            "rainfall_probability": 20.0,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_MONITOR


class TestRulePriority:
    """Test that rule priority is strictly maintained when multiple conditions are met."""

    def test_rule_1_takes_priority_over_rule_4(self):
        """
        If soil is dry (<30%), but humidity > 75% AND rain > 60%,
        Rule 1 (STOP) must trigger before Rule 4 (IRRIGATE).
        """
        reading = {
            "soil_moisture": 10.0,  # Would match Rule 4
            "temperature": 26.0,
            "humidity": 80.0,  # Matches Rule 1
            "rainfall_probability": 70.0,  # Matches Rule 1
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_STOP
        assert "Rule 1" in res.reason

    def test_rule_1_takes_priority_over_rule_2(self):
        """
        If humidity > 75% AND rain > 60% AND soil >= 60%,
        Rule 1 must trigger first.
        """
        reading = {
            "soil_moisture": 80.0,  # Matches Rule 2
            "temperature": 24.0,
            "humidity": 85.0,  # Matches Rule 1
            "rainfall_probability": 90.0,  # Matches Rule 1
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_STOP
        assert "Rule 1" in res.reason

    def test_rule_2_takes_priority_over_rule_3(self):
        """
        Soil >= 60% with rain >= 50% (and humidity <= 75%).
        Rule 2 (STOP) must trigger before any other rule.
        """
        reading = {
            "soil_moisture": 65.0,
            "temperature": 20.0,
            "humidity": 60.0,
            "rainfall_probability": 55.0,
        }
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_STOP
        assert "Rule 2" in res.reason


class TestBoundaryValues:
    """Test boundary conditions for valid readings."""

    def test_sensor_reading_object_input(self):
        """Ensure SensorReading dataclass works seamlessly as input."""
        reading = SensorReading(
            soil_moisture=15.0,
            temperature=25.0,
            humidity=50.0,
            rainfall_probability=20.0,
        )
        res = evaluate_sensor_readings(reading)
        assert res.action == ACTION_IRRIGATE
        assert res.duration_minutes == 15

    def test_physical_extremes(self):
        """Test exact valid boundary extremes: 0%, 100%, -10°C, 60°C."""
        # Minimum physical bounds
        reading_min = {
            "soil_moisture": 0.0,
            "temperature": -10.0,
            "humidity": 0.0,
            "rainfall_probability": 0.0,
        }
        res_min = evaluate_sensor_readings(reading_min)
        assert res_min.action == ACTION_IRRIGATE  # Dry soil < 30%, rain < 50%

        # Maximum physical bounds
        reading_max = {
            "soil_moisture": 100.0,
            "temperature": 60.0,
            "humidity": 100.0,
            "rainfall_probability": 100.0,
        }
        res_max = evaluate_sensor_readings(reading_max)
        assert res_max.action == ACTION_STOP  # Rule 1 triggers


class TestValidationAndErrorHandling:
    """Test strict validation and rejection of invalid values."""

    def test_negative_soil_moisture(self):
        with pytest.raises(ValueError, match="Soil moisture"):
            evaluate_sensor_readings(
                {"soil_moisture": -1.0, "temperature": 25.0, "humidity": 50.0, "rainfall_probability": 20.0}
            )

    def test_over_limit_humidity(self):
        with pytest.raises(ValueError, match="Humidity"):
            evaluate_sensor_readings(
                {"soil_moisture": 50.0, "temperature": 25.0, "humidity": 100.1, "rainfall_probability": 20.0}
            )

    def test_sub_zero_extreme_temperature(self):
        with pytest.raises(ValueError, match="Temperature"):
            evaluate_sensor_readings(
                {"soil_moisture": 50.0, "temperature": -10.5, "humidity": 50.0, "rainfall_probability": 20.0}
            )

    def test_over_limit_temperature(self):
        with pytest.raises(ValueError, match="Temperature"):
            evaluate_sensor_readings(
                {"soil_moisture": 50.0, "temperature": 60.1, "humidity": 50.0, "rainfall_probability": 20.0}
            )

    def test_invalid_types_and_booleans(self):
        # Booleans must be rejected
        with pytest.raises(ValueError, match="boolean"):
            evaluate_sensor_readings(
                {"soil_moisture": True, "temperature": 25.0, "humidity": 50.0, "rainfall_probability": 20.0}
            )

        # Strings that cannot convert
        with pytest.raises(ValueError, match="numeric"):
            evaluate_sensor_readings(
                {"soil_moisture": "dry", "temperature": 25.0, "humidity": 50.0, "rainfall_probability": 20.0}
            )

    def test_safe_evaluate_readings_returns_error(self):
        """Ensure safe_evaluate_readings never raises and returns ACTION_ERROR with duration 0."""
        res = safe_evaluate_readings({"soil_moisture": -50.0, "temperature": 25.0, "humidity": 50.0, "rainfall_probability": 20.0})
        assert res.action == ACTION_ERROR
        assert res.duration_minutes == 0
        assert "Validation error" in res.reason
