"""
app.py
======
Gradio Web Interface for the Smart Irrigation Autonomous Agent.

Features:
- Live display of Agent status (RUNNING / STOPPED) and Irrigation status (ON / OFF).
- Real-time countdown of remaining irrigation duration.
- Environmental sensor readings and latest rule-based decision explanation.
- Interactive controls: Start Agent, Stop Agent, Refresh Reading, Stop Irrigation.
- Manual scenario testing panel with presets and custom sliders.
- Live-updating decision history table with bounded records.
- Completely local execution on 127.0.0.1 without external web dependencies.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Tuple

# Ensure project root is available in module path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import gradio as gr
from agent import IrrigationAgent
from controller import IrrigationController

# Singleton Agent Instance for the application lifecycle
controller = IrrigationController(time_scale=1.0)
agent = IrrigationAgent(controller=controller, interval_seconds=5.0)


def format_status_badge(status: str, active_val: str, active_color: str = "#22c55e", inactive_color: str = "#64748b") -> str:
    color = active_color if status == active_val else inactive_color
    return f"""<div style="display:inline-block; padding: 6px 16px; border-radius: 9999px; background-color: {color}; color: white; font-weight: 700; font-size: 1.1rem; text-align: center; letter-spacing: 0.05em; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">{status}</div>"""


def format_action_badge(action: str) -> str:
    color_map = {
        "IRRIGATE": "#0284c7",  # Bright Sky Blue
        "STOP": "#ef4444",      # Vivid Red
        "WAIT": "#f59e0b",      # Amber
        "MONITOR": "#10b981",   # Emerald Green
        "ERROR": "#dc2626",     # Crimson
    }
    color = color_map.get(action, "#64748b")
    return f"""<div style="display:inline-block; padding: 6px 16px; border-radius: 8px; background-color: {color}; color: white; font-weight: 700; font-size: 1.1rem; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">{action}</div>"""


def get_dashboard_state() -> Tuple[str, str, str, str, str, str, str, str, str, str, str, List[List[Any]]]:
    """Gather live state from the agent and controller to refresh the UI."""
    status = agent.get_status()
    reading = status.get("latest_reading") or {}
    decision = status.get("latest_decision") or {}

    agent_badge = format_status_badge(status["agent_status"], "RUNNING", "#16a34a", "#64748b")
    irrigation_badge = format_status_badge(status["controller_status"], "ON", "#0284c7", "#64748b")
    remaining_time = status.get("remaining_time", "0m 00s")
    
    action_raw = decision.get("action", "MONITOR")
    action_badge = format_action_badge(action_raw)
    duration_str = f"{decision.get('duration_minutes', 0)} min"
    reason_str = decision.get("reason", "Awaiting sensor reading...")

    sm_val = f"{reading.get('soil_moisture', 0.0):.1f}%"
    temp_val = f"{reading.get('temperature', 0.0):.1f}°C"
    hum_val = f"{reading.get('humidity', 0.0):.1f}%"
    rain_val = f"{reading.get('rainfall_probability', 0.0):.1f}%"
    source_val = f"Source: {reading.get('source', 'simulated').capitalize()}"

    # Build history table
    history_entries = agent.get_history(limit=50)
    history_rows = []
    for entry in history_entries:
        history_rows.append([
            entry.get("Timestamp", ""),
            entry.get("Soil Moisture (%)", ""),
            entry.get("Temperature (°C)", ""),
            entry.get("Humidity (%)", ""),
            entry.get("Rainfall Prob (%)", ""),
            entry.get("Action", ""),
            entry.get("Duration", ""),
            entry.get("Irrigation", ""),
            entry.get("Remaining", ""),
            entry.get("Source", ""),
            entry.get("Reason", ""),
        ])

    return (
        agent_badge,
        irrigation_badge,
        remaining_time,
        action_badge,
        duration_str,
        reason_str,
        sm_val,
        temp_val,
        hum_val,
        rain_val,
        source_val,
        history_rows,
    )


# Handlers for interactive controls
def handle_start_agent() -> str:
    started = agent.start()
    return "Agent started successfully (Monitoring every ~5s)." if started else "Agent is already running."


def handle_stop_agent() -> str:
    stopped = agent.stop()
    return "Agent stopped. Irrigation turned OFF." if stopped else "Agent is already stopped (Irrigation ensured OFF)."


def handle_refresh_cycle() -> str:
    decision = agent.run_cycle(source="simulated")
    return f"Simulated cycle executed: Recommended {decision.action} ({decision.duration_minutes}m)."


def handle_emergency_stop() -> str:
    ok, msg = controller.stop_irrigation(reason="Manual emergency stop via UI")
    return msg


def handle_evaluate_manual(
    soil_moisture: float,
    temperature: float,
    humidity: float,
    rainfall_probability: float,
    apply_to_controller: bool,
) -> Tuple[str, str, str]:
    decision = agent.evaluate_manual_scenario(
        soil_moisture=float(soil_moisture),
        temperature=float(temperature),
        humidity=float(humidity),
        rainfall_probability=float(rainfall_probability),
        apply_to_controller=apply_to_controller,
    )

    action_text = f"Action: **{decision.action}** | Duration: **{decision.duration_minutes} min**"
    details = f"**Rationale:** {decision.reason}"
    status_notice = (
        "✅ Scenario evaluated and applied to controller & history."
        if apply_to_controller
        else "ℹ️ Scenario evaluated (dry-run mode, controller unchanged)."
    )
    return action_text, details, status_notice


def apply_preset(preset_name: str) -> Tuple[float, float, float, float]:
    presets = {
        "Rule 1: High Humidity (>75%) & High Rain (>60%)": (25.0, 28.0, 80.0, 65.0),
        "Rule 2: Sufficient Soil Moisture (>=60%)": (65.0, 26.0, 45.0, 20.0),
        "Rule 3: Dry Soil (<30%) & Rain Expected (>=50%)": (20.0, 29.0, 55.0, 60.0),
        "Rule 4: Critically Dry Soil (<30%) & Low Rain (<50%)": (18.0, 27.0, 40.0, 15.0),
        "Rule 5: Moderate Moisture (30-45%), High Temp (>32°C), Low Rain (<40%)": (38.0, 35.0, 35.0, 20.0),
        "Rule 6: Balanced Conditions (Routine Monitoring)": (50.0, 24.0, 50.0, 10.0),
    }
    return presets.get(preset_name, (25.0, 30.0, 50.0, 20.0))


# Build Gradio UI
with gr.Blocks(title="🌱 Smart Irrigation Autonomous Agent") as demo:
    gr.Markdown(
        """
        # 🌱 Smart Irrigation Autonomous Agent
        ### Autonomous Agricultural Assistant with Simulated Sensors & Decision Engine
        *Maintains optimal crop soil moisture while conserving water using real-time condition-action rules.*
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("#### Agent Status")
            agent_status_html = gr.HTML(format_status_badge("STOPPED", "RUNNING"))
        with gr.Column(scale=1):
            gr.Markdown("#### Irrigation State")
            irrigation_status_html = gr.HTML(format_status_badge("OFF", "ON", "#0284c7"))
        with gr.Column(scale=1):
            gr.Markdown("#### Irrigation Countdown")
            countdown_box = gr.Textbox(value="0m 00s", label="Remaining Time", interactive=False)
        with gr.Column(scale=1):
            gr.Markdown("#### Recommended Action")
            action_status_html = gr.HTML(format_action_badge("MONITOR"))
            duration_box = gr.Textbox(value="0 min", label="Recommended Duration", interactive=False)

    with gr.Row():
        with gr.Column(scale=3):
            reason_box = gr.Textbox(
                label="Latest Decision Explanation",
                value="System initialized. Click 'Start Agent' to begin background monitoring.",
                interactive=False,
                lines=2,
            )
        with gr.Column(scale=1):
            source_indicator = gr.Textbox(label="Reading Mode", value="Source: Initialized", interactive=False)

    gr.Markdown("### 📡 Live Simulated Environmental Sensors")
    with gr.Row():
        sm_metric = gr.Textbox(label="💧 Soil Moisture (%)", value="0.0%", interactive=False)
        temp_metric = gr.Textbox(label="🌡️ Temperature (°C)", value="0.0°C", interactive=False)
        hum_metric = gr.Textbox(label="💨 Humidity (%)", value="0.0%", interactive=False)
        rain_metric = gr.Textbox(label="🌧️ Rainfall Probability (%)", value="0.0%", interactive=False)

    gr.Markdown("### 🎮 Control Center")
    with gr.Row():
        start_btn = gr.Button("▶️ Start Agent", variant="primary", size="lg")
        stop_btn = gr.Button("⏹️ Stop Agent", variant="secondary", size="lg")
        refresh_btn = gr.Button("🔄 Step / Refresh Reading", size="lg")
        emergency_btn = gr.Button("🛑 Stop Irrigation", variant="stop", size="lg")

    control_feedback = gr.Markdown(value="*System ready.*")

    with gr.Accordion("🧪 Manual Scenario Testing & Rule Verification", open=False):
        gr.Markdown(
            "Quickly verify decision rules by choosing a preset scenario or adjusting values manually."
        )
        preset_dropdown = gr.Dropdown(
            label="Load Scenario Preset",
            choices=[
                "Rule 1: High Humidity (>75%) & High Rain (>60%)",
                "Rule 2: Sufficient Soil Moisture (>=60%)",
                "Rule 3: Dry Soil (<30%) & Rain Expected (>=50%)",
                "Rule 4: Critically Dry Soil (<30%) & Low Rain (<50%)",
                "Rule 5: Moderate Moisture (30-45%), High Temp (>32°C), Low Rain (<40%)",
                "Rule 6: Balanced Conditions (Routine Monitoring)",
            ],
            value="Rule 4: Critically Dry Soil (<30%) & Low Rain (<50%)",
        )

        with gr.Row():
            manual_sm = gr.Slider(0.0, 100.0, value=18.0, step=0.5, label="Soil Moisture (%)")
            manual_temp = gr.Slider(-10.0, 60.0, value=27.0, step=0.5, label="Temperature (°C)")
            manual_hum = gr.Slider(0.0, 100.0, value=40.0, step=0.5, label="Humidity (%)")
            manual_rain = gr.Slider(0.0, 100.0, value=15.0, step=0.5, label="Rainfall Probability (%)")

        with gr.Row():
            apply_checkbox = gr.Checkbox(
                label="Apply Decision to Irrigation Controller & Record to History",
                value=False,
            )
            evaluate_btn = gr.Button("Evaluate Scenario", variant="primary")

        with gr.Row():
            scenario_action_out = gr.Markdown("Action: -")
            scenario_status_out = gr.Markdown("")
        scenario_reason_out = gr.Markdown("Explanation: -")

    gr.Markdown("### 📜 Autonomous Decision History (Latest 50 Entries)")
    history_table = gr.Dataframe(
        headers=[
            "Timestamp",
            "Soil Moisture (%)",
            "Temperature (°C)",
            "Humidity (%)",
            "Rainfall Prob (%)",
            "Action",
            "Duration",
            "Irrigation",
            "Remaining",
            "Source",
            "Reason",
        ],
        datatype=["str"] * 11,
        value=[],
        interactive=False,
    )

    # Periodic background UI updater (2.0s interval)
    refresh_timer = gr.Timer(value=2.0)
    refresh_timer.tick(
        fn=get_dashboard_state,
        inputs=[],
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )

    # Event Handlers
    start_btn.click(fn=handle_start_agent, outputs=[control_feedback]).then(
        fn=get_dashboard_state,
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )

    stop_btn.click(fn=handle_stop_agent, outputs=[control_feedback]).then(
        fn=get_dashboard_state,
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )

    refresh_btn.click(fn=handle_refresh_cycle, outputs=[control_feedback]).then(
        fn=get_dashboard_state,
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )

    emergency_btn.click(fn=handle_emergency_stop, outputs=[control_feedback]).then(
        fn=get_dashboard_state,
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )

    preset_dropdown.change(
        fn=apply_preset,
        inputs=[preset_dropdown],
        outputs=[manual_sm, manual_temp, manual_hum, manual_rain],
    )

    evaluate_btn.click(
        fn=handle_evaluate_manual,
        inputs=[manual_sm, manual_temp, manual_hum, manual_rain, apply_checkbox],
        outputs=[scenario_action_out, scenario_reason_out, scenario_status_out],
    ).then(
        fn=get_dashboard_state,
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )

    # Initial load of dashboard state
    demo.load(
        fn=get_dashboard_state,
        outputs=[
            agent_status_html,
            irrigation_status_html,
            countdown_box,
            action_status_html,
            duration_box,
            reason_box,
            sm_metric,
            temp_metric,
            hum_metric,
            rain_metric,
            source_indicator,
            history_table,
        ],
    )


def main() -> None:
    """Launch the Gradio interface locally."""
    print("🌱 Starting Smart Irrigation Autonomous Agent Web Interface...")
    print("📍 Local address: http://127.0.0.1:7860")
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
