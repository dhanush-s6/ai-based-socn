# LTE-AI SON Installation and Run Guide

## 1. Prerequisites

Required on Ubuntu/Linux:
1. Python 3.10+ (project tested with Python 3.12).
2. NS-3 source/build available at `../ns-3-dev`.
3. GCC/Clang toolchain for NS-3 build.
4. `pip` and virtual environment support.

## 2. Project Setup

From project root (`/home/darkdevil/Desktop/lte-ai-project`):

```bash
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. NS-3 Build

Build simulator from NS-3 root:

```bash
cd /home/darkdevil/Desktop/ns-3-dev
ns3 build
```

If `ns3` is not in PATH, run:

```bash
./ns3 build
```

## 4. Runtime Start Order

Start in this order in separate terminals.

### Terminal 1: AI Server

```bash
cd /home/darkdevil/Desktop/lte-ai-project
source env/bin/activate
python ai_server.py
```

### Terminal 2: Dashboard

```bash
cd /home/darkdevil/Desktop/lte-ai-project
source env/bin/activate
python dashboard/app.py
```

Open:
- `http://127.0.0.1:8050`

### Terminal 3: NS-3 Simulator

```bash
cd /home/darkdevil/Desktop/ns-3-dev
ns3 run "lte_ai_simulator_2000ues --numUe=2000 --simTime=1800 --kpiInterval=1.0"
```

For fast tests:

```bash
ns3 run "lte_ai_simulator_2000ues --numUe=10 --simTime=120 --kpiInterval=1.0"
```

## 5. Runtime Controls

From dashboard:
1. Inject errors using the Error Injection panel.
2. Start/stop individual eNBs.
3. Use `AI Action` button to:
   - Start all eNBs.
   - Trigger immediate rebalance.

## 6. Important Runtime Files

1. KPI CSV output:
   - `/home/darkdevil/Desktop/ns-3-dev/city_kpi_dataset.csv`
2. AI decisions log:
   - `/home/darkdevil/Desktop/lte-ai-project/ai_decisions.log`

## 7. Retraining Model (Optional)

Manual retrain from current dataset:

```bash
cd /home/darkdevil/Desktop/lte-ai-project
source env/bin/activate
python - <<'PY'
from ai_engine.hybrid_predictor import HybridPredictor
p = HybridPredictor()
p.train('training_dataset.csv')
p.save('models/network_ai_hybrid.pkl')
print('model retrained')
PY
```

## 8. Troubleshooting

1. Dashboard not updating:
   - Verify KPI CSV is being written in NS-3 terminal.
2. Control buttons not working:
   - Ensure NS-3 is running and control port `5002` is active.
3. Injection not working:
   - Ensure NS-3 injection port `5001` is reachable.
4. AI fallback actions only:
   - Check model load logs in AI server startup output.

## 9. Stop All Services

Use `Ctrl+C` in each terminal.
