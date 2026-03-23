# AI-Based SON for LTE (NS-3 + Hybrid AI + Dashboard)

This repository contains an end-to-end AI-driven Self-Organizing Network (SON) workflow for LTE simulation.

It combines:
- `ns-3` simulation scenarios and custom LTE programs.
- A Python AI server that receives KPI vectors and returns per-cell actions.
- A Dash-based control and monitoring dashboard.
- Error injection and eNB control channels for closed-loop testing.

## Workspace Layout

This workspace has two major folders:

- `lte-ai-project/`: Python-side AI, control, training, and dashboard modules.
- `ns-3-dev/`: NS-3 source tree, build system, and custom LTE simulation programs.

Important custom NS-3 programs are in:
- `ns-3-dev/scratch/lte_ai_simulator_2000ues.cc`
- `ns-3-dev/scratch/lte_ai_dataset_generator.cc`

## System Architecture

Closed-loop flow:

1. NS-3 computes KPIs for 6 eNBs every interval.
2. NS-3 sends a 42-value KPI vector to the AI server on `127.0.0.1:5000`.
3. The AI server predicts actions using the hybrid model.
4. Stability and safety constraints post-process raw actions.
5. AI server returns 6 actions to NS-3.
6. Dashboard visualizes KPIs and decisions, and can inject faults or control eNB state.

Ports in use:

- `5000`: NS-3 <-> AI server KPI/action socket.
- `5001`: Dashboard -> NS-3 error injection channel.
- `5002`: Dashboard -> NS-3 control channel (`START`, `STOP`, `REBALANCE`/AI action).
- `8050`: Dashboard web UI.

## Core Components

### AI Server

File: `lte-ai-project/ai_server.py`

Responsibilities:
- Load or train the hybrid predictor.
- Process incoming 42-feature KPI vectors.
- Apply `StabilityController` and `ActionValidator` safeguards.
- Return action vectors to NS-3.
- Log decisions to `ai_decisions.log`.

### AI Engine

Folder: `lte-ai-project/ai_engine/`

Key modules:
- `hybrid_predictor.py`: Isolation Forest + Gradient Boosting + neighbor-aware augmentation.
- `smart_labeler.py`: rule-based SON labels for training.
- `neighbor_manager.py`: neighbor topology and load-balance heuristics.
- `stability_controller.py`: cooldown/hysteresis/anti-oscillation.
- `action_validator.py`: post-action policy and safety constraints.
- `model_updater.py`: optional continuous retraining monitor.

Action IDs:
- `0`: BALANCE
- `1`: INCREASE_POWER
- `2`: REDUCE_POWER
- `3`: HANDOVER

### Dashboard

File: `lte-ai-project/dashboard/app.py`

Features:
- Live KPI graphs (throughput, delay, loss, SINR, RSRP).
- Load-balancing score visualization.
- AI decision log panel.
- Error injection controls.
- eNB start/stop and AI action trigger controls.

## Prerequisites

- Linux environment (project scripts are Linux-oriented).
- Python 3.10+ (3.12 is used in setup scripts).
- NS-3 source tree available in `ns-3-dev/`.
- C/C++ build toolchain for NS-3.

## Quick Start

### 1. Python environment

From workspace root:

```bash
cd lte-ai-project
python3 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

You can also run:

```bash
cd lte-ai-project
bash setup.sh
```

### 2. Build NS-3

```bash
cd ns-3-dev
./ns3 configure
./ns3 build
```

### 3. Start services (3 terminals)

Terminal 1 (AI server):

```bash
cd lte-ai-project
source env/bin/activate
python ai_server.py
```

Terminal 2 (Dashboard):

```bash
cd lte-ai-project
source env/bin/activate
python dashboard/app.py
```

Open: `http://127.0.0.1:8050`

Terminal 3 (NS-3 simulator):

```bash
cd ns-3-dev
./ns3 run "lte_ai_simulator_2000ues --numUe=2000 --simTime=1800 --kpiInterval=1.0"
```

Fast test run:

```bash
./ns3 run "lte_ai_simulator_2000ues --numUe=10 --simTime=120 --kpiInterval=1.0"
```

## Training and Retraining

### Dataset generation from NS-3

```bash
cd ns-3-dev
./ns3 run "lte_ai_dataset_generator --numUe=500 --simTime=600"
```

### Train hybrid model

```bash
cd lte-ai-project
source env/bin/activate
python train_model.py
```

### Optional quick helper

```bash
cd lte-ai-project
bash QUICK_TRAIN.sh
```

The model updater can retrain continuously based on `config/config.yaml`:
- `model_updater.enabled`
- `model_updater.retraining_interval`

## Data and Logs

Primary runtime artifacts:
- KPI data: `lte-ai-project/data/city_kpi_dataset.csv` (or NS-3 path in config).
- Training data: `lte-ai-project/data/training_dataset.csv`.
- AI decision logs: `lte-ai-project/ai_decisions.log`.
- Models: `lte-ai-project/models/`.
- Model backups: `lte-ai-project/models/backups/`.

## Configuration

Main config file:

- `lte-ai-project/config/config.yaml`

Useful keys:
- `ai_engine.server_host`, `ai_engine.server_port`
- `dashboard.host`, `dashboard.port`
- `simulator.kpi_output_csv`
- `model_updater.*`

Environment template:

- `lte-ai-project/.env.example`

## Error Injection and Control

From the dashboard you can:
- Inject network issues (`congestion`, `interference`, `ddos`, etc.).
- Start/stop specific eNBs.
- Trigger AI action sequence (start all + rebalance request).

Error semantics are defined in:
- `lte-ai-project/simulator/error_definitions.py`
- `lte-ai-project/simulator/error_injector.py`

## Troubleshooting

1. Dashboard has no data:
- Check the NS-3 simulator is running.
- Verify KPI CSV is being written.

2. Dashboard controls fail:
- Confirm NS-3 control sockets are active on ports `5001` and `5002`.

3. AI server returns fallback actions:
- Check model load/train logs in AI server startup.
- Verify model exists at configured `hybrid_model_path`.

4. Feature mismatch errors:
- Ensure NS-3 output format and model feature expectations are aligned (42 KPI inputs).
- Retrain model after dataset/schema changes.

## Development Notes

- `controller/` and `interface/` include simpler legacy helpers and are not the main runtime path.
- The recommended operational path is:
	- NS-3 custom simulator in `ns-3-dev/scratch/`
	- AI server in `lte-ai-project/ai_server.py`
	- Dashboard in `lte-ai-project/dashboard/app.py`

## Documentation References

- `lte-ai-project/ARCHITECTURE.md`
- `lte-ai-project/INSTALLATION.md`
- `ns-3-dev/README.md`

