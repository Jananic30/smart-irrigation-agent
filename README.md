# 🌱 Smart Irrigation Autonomous Agent

An intelligent, rule-based autonomous agent that continuously monitors simulated environmental conditions and controls irrigation to maintain healthy crop soil moisture while minimizing water waste.

> **Coursework & Simulation Notice**  
> This project is designed for local coursework demonstration on macOS. All sensor readings and irrigation operations are **purely simulated in software**. No physical irrigation valves, relays, or hardware are operated, and no live external weather services are connected.

---

## 📌 1. Project Overview & Objective

The **Smart Irrigation Autonomous Agent** acts as an automated agricultural decision maker. In traditional farming, irrigation is often applied on a fixed timer regardless of actual soil moisture or upcoming rainfall, leading to severe water waste and soil waterlogging. 

This autonomous agent continuously monitors key micro-climate factors:
1. **Soil Moisture (%)**
2. **Ambient Temperature (°C)**
3. **Relative Humidity (%)**
4. **Rainfall Probability (%)**

Based on validated condition-action rules, the agent determines the appropriate action:
- **`IRRIGATE`**: Activate irrigation for 10 or 15 minutes when soil is dry and natural rain is unlikely.
- **`STOP`**: Immediately halt or prevent irrigation when soil is already sufficiently moist or rain is imminent.
- **`WAIT`**: Delay irrigation even if soil is dry when rainfall is expected soon, conserving resources.
- **`MONITOR`**: Continue background surveillance when conditions are within acceptable thresholds.

---

## 🏗️ 2. File-by-File Architecture

```
smart-irrigation-agent/
├── main.py                 # Core rule-based decision engine and input validation
├── sensors.py              # Simulated sensor generation, data structures, and boundaries
├── controller.py           # Thread-safe simulated irrigation controller with monotonic countdown
├── agent.py                # Autonomous monitoring background thread, state, and bounded history
├── app.py                  # Gradio interactive web dashboard and control panel
├── requirements.txt        # Pinned project dependencies
├── README.md               # Complete setup, testing, and architecture documentation
├── .gitignore              # Ignores .venv, cache files, and test artifacts
└── tests/                  # Automated pytest test suite
    ├── conftest.py         # Pytest configuration ensuring project root is in sys.path
    ├── test_decisions.py   # Unit tests for rules, priorities, and validation boundaries
    ├── test_controller.py  # Unit tests for controller safety, countdown, and session overlap prevention
    └── test_agent.py       # Unit tests for autonomous agent lifecycle and history recording
```

### Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`sensors.py`** | Defines `SensorReading` dataclass and physical validation rules. Simulates realistic natural sensor drifts and variations. |
| **`main.py`** | Evaluates sensor readings against the 6 condition-action rules in strict priority order. Produces `DecisionResult` objects. |
| **`controller.py`** | Simulates irrigation hardware with thread-safe locks (`threading.RLock`) and monotonic timing (`time.monotonic()`). Prevents overlapping sessions and enforces a 15-minute maximum session cap. |
| **`agent.py`** | Coordinates background monitoring on an independent thread, updates controller state, handles errors gracefully, and maintains a bounded circular buffer (latest 500 entries) for history. |
| **`app.py`** | Clean Gradio web UI allowing users to start/stop the agent, trigger manual readings, test custom scenarios, and view real-time countdowns. |

---

## 📊 3. Simulated Sensors & Supported Ranges

| Sensor Metric | Units | Valid Range | Physical Interpretation |
| :--- | :---: | :---: | :--- |
| **Soil Moisture** | `%` | `0.0%` to `100.0%` | Volumetric soil water content. `< 30%` is dry; `>= 60%` is fully saturated. |
| **Temperature** | `°C` | `-10.0°C` to `60.0°C` | Ambient air temperature. High heat (`> 32°C`) accelerates soil evaporation. |
| **Relative Humidity** | `%` | `0.0%` to `100.0%` | Atmospheric moisture content. High humidity (`> 75%`) often precedes precipitation. |
| **Rainfall Probability** | `%` | `0.0%` to `100.0%` | Estimated likelihood of imminent natural rainfall. |

> **Safety Rule**: Any input outside these ranges or non-numeric values are rejected by the validator and **never trigger irrigation**.

---

## ⚖️ 4. Decision Rules & Priority Order

The decision engine applies condition-action rules in **strict priority order**:

| Priority | Rule | Condition | Recommended Action | Duration | Justification |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | **High Humidity & High Rain** | `humidity > 75%` **AND** `rainfall_probability > 60%` | **`STOP`** | `0 min` | Imminent natural rain will hydrate soil; shut off irrigation to prevent runoff and conserve water. |
| **2** | **Sufficient Soil Moisture** | `soil_moisture >= 60%` | **`STOP`** | `0 min` | Soil moisture is already optimal or saturated; irrigation is unnecessary and risks root rot. |
| **3** | **Dry Soil, High Rain Chance** | `soil_moisture < 30%` **AND** `rainfall_probability >= 50%` | **`WAIT`** | `0 min` | Soil is dry, but natural precipitation is expected soon. Wait for rain before consuming water. |
| **4** | **Dry Soil, Low Rain Chance** | `soil_moisture < 30%` **AND** `rainfall_probability < 50%` | **`IRRIGATE`** | `15 min` | Soil is critically dry and rain is unlikely. Full 15-minute irrigation session required. |
| **5** | **Moderate Soil, High Heat** | `30% <= soil_moisture <= 45%` **AND** `temperature > 32°C` **AND** `rainfall_probability < 40%` | **`IRRIGATE`** | `10 min` | High heat causes rapid evapotranspiration. Supplementary 10-minute irrigation maintains moisture. |
| **6** | **Default Monitoring** | All other conditions | **`MONITOR`** | `0 min` | Environmental parameters are balanced; continue routine surveillance. |

---

## 🚀 5. Installation & Local Setup (macOS)

### Prerequisites
- macOS on a MacBook
- Python 3.12 (specifically Python 3.12.7 recommended)

### Step 1: Open the Project Directory
```bash
cd /Users/jananijan/Desktop/smart-irrigation-agent
```

### Step 2: Activate the Virtual Environment
The project includes a Python 3.12 virtual environment at `.venv`:
```bash
source .venv/bin/activate
```
*(Verify Python version: `python --version` should display `Python 3.12.x`)*

### Step 3: Install Required Packages
```bash
pip install -r requirements.txt
```

---

## 🧪 6. Running Automated Tests

Run the full automated test suite using `pytest`:

```bash
# Run all tests with verbose output
.venv/bin/pytest tests -v
```

### Test Suite Structure
- **`tests/test_decisions.py`**:
  - Verifies all 6 rules under standard and boundary conditions.
  - Verifies rule precedence when multiple conditions are satisfied simultaneously.
  - Confirms validation rejects negatives, overflows, and non-numeric inputs.
- **`tests/test_controller.py`**:
  - Tests safe session activation and countdown tracking using monotonic time.
  - Verifies rejection of invalid or excessive durations (>15 min).
  - Confirms automatic shutdown after time expires and prevention of overlapping sessions.
- **`tests/test_agent.py`**:
  - Verifies agent start/stop lifecycle and idempotency (prevents duplicate threads).
  - Ensures irrigation is forced OFF whenever the agent stops.
  - Verifies decision logging to the bounded history buffer.

---

## 🖥️ 7. Operating the Gradio Web Dashboard

### Launching the Dashboard
Execute:
```bash
.venv/bin/python app.py
```
Or with the active virtual environment:
```bash
python app.py
```

Open your browser to:
👉 **`http://127.0.0.1:7860`**

### Dashboard Features & Controls
1. **Agent & Irrigation Status Badges**: Real-time status pills (`RUNNING` / `STOPPED`, `ON` / `OFF`).
2. **Irrigation Countdown**: Shows live remaining time (e.g. `14m 32s`) updated every 2 seconds without UI freeze.
3. **Recommended Action & Rationale**: Explains the exact rule and sensor thresholds that triggered the latest action.
4. **Live Sensor Cards**: Real-time readings of Soil Moisture, Temperature, Humidity, and Rainfall Probability.
5. **Control Buttons**:
   - `▶️ Start Agent`: Launches the autonomous background thread (monitors every ~5 seconds).
   - `⏹️ Stop Agent`: Gracefully halts monitoring and turns simulated irrigation OFF.
   - `🔄 Step / Refresh Reading`: Immediately generates a new simulated cycle.
   - `🛑 Stop Irrigation`: Manual emergency stop button to instantly shut off simulated irrigation.
6. **Manual Scenario Testing Panel**:
   - Use the preset dropdown (e.g., *Rule 1*, *Rule 4*, *Rule 5*) to populate realistic scenarios.
   - Adjust sliders manually to test custom boundary cases.
   - Check *"Apply Decision to Irrigation Controller"* if you wish the test to directly alter system state.
7. **Autonomous Decision History**: Table showing the latest 50 decisions with full timestamps, metrics, actions, and explanations.

---

## 📋 8. Example Scenarios & Expected Decisions

| Scenario Description | Soil Moisture | Temperature | Humidity | Rain Prob | Expected Action | Expected Duration |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Heavy Storm Approaching** | 22.0% | 24.0°C | 82.0% | 75.0% | **`STOP`** | `0 min` |
| **Well-Watered Soil** | 68.0% | 27.0°C | 50.0% | 10.0% | **`STOP`** | `0 min` |
| **Dry Field, Rain Expected** | 20.0% | 28.0°C | 60.0% | 55.0% | **`WAIT`** | `0 min` |
| **Severe Drought / Parched Soil** | 15.0% | 30.0°C | 35.0% | 10.0% | **`IRRIGATE`** | `15 min` |
| **Mid-Day Heat Wave** | 38.0% | 36.0°C | 30.0% | 15.0% | **`IRRIGATE`** | `10 min` |
| **Mild Spring Morning** | 52.0% | 22.0°C | 55.0% | 20.0% | **`MONITOR`** | `0 min` |

---

## 🔧 9. Troubleshooting & Common Questions

### 1. `ModuleNotFoundError: No module named 'gradio'` or `'pytest'`
Ensure you are using the virtual environment interpreter:
```bash
/Users/jananijan/Desktop/smart-irrigation-agent/.venv/bin/python app.py
```
Or activate the environment first: `source .venv/bin/activate`.

### 2. Address Already in Use (`Port 7860`)
If another instance of Gradio is running on port 7860, find and terminate it:
```bash
lsof -i :7860
kill -9 <PID>
```

### 3. Agent Thread Lifecycle
The monitoring thread runs as a Python `daemon=True` thread managed by an explicit `threading.Event` stop signal. Clicking **`⏹️ Stop Agent`** signals the thread to terminate and calls `controller.stop_irrigation()`, ensuring no orphaned processes or ongoing sessions remain.

---

## 🔒 10. Scope & Safety Protections

- **Physical Isolation**: This application contains zero hardware drivers or GPIO pins.
- **Fail-Safe Defaults**: If invalid or corrupted sensor data is supplied, irrigation is immediately shut OFF and an `ACTION_ERROR` is logged.
- **Overlapping Prevention**: Starting an irrigation session while one is active will not restart the timer or corrupt controller state.
- **Bounded Memory**: Decision history is stored in a fixed-size `collections.deque(maxlen=500)` to prevent unbounded memory growth during continuous operation.
