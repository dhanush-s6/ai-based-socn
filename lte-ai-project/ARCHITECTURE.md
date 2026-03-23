# LTE-AI SON Architecture

## 1. System Overview
This project is a closed-loop Self-Organizing Network (SON) control system built on top of NS-3 LTE simulation.

The loop is:
1. NS-3 computes per-cell KPI metrics every second.
2. NS-3 sends KPI vectors to the AI server over TCP (`127.0.0.1:5000`).
3. AI server predicts actions, applies stability and safety constraints, and returns 6 actions (one per eNB).
4. NS-3 applies actions (power/handover behavior) and updates network state.
5. Dashboard visualizes KPIs, load balancing score, AI decisions, and allows operator control.

## 2. Runtime Components

### NS-3 Simulator
File: `../ns-3-dev/scratch/lte_ai_simulator_2000ues.cc`

Responsibilities:
1. Simulate LTE topology (6 eNBs, configurable UE count).
2. Compute and log KPI values to `../ns-3-dev/city_kpi_dataset.csv`.
3. Send 42-feature KPI vector to AI server each interval.
4. Receive and apply AI actions.
5. Expose control sockets:
   - `5001`: error injection.
   - `5002`: eNB control (`START`, `STOP`, `REBALANCE`).

### AI Server
File: `ai_server.py`

Responsibilities:
1. Receive KPI vectors from NS-3.
2. Run `HybridPredictor` inference.
3. Apply `StabilityController` to prevent oscillations/handover spam.
4. Apply `ActionValidator` constraints before execution.
5. Return action vector to NS-3.
6. Persist detailed decision logs to `ai_decisions.log`.

### AI Engine Modules
Folder: `ai_engine/`

Key modules:
1. `hybrid_predictor.py`
   - Isolation Forest anomaly scoring.
   - Gradient Boosting trend/action hints.
   - Neighbor-aware feature augmentation.
   - Load-balancing policy stage.
2. `neighbor_manager.py`
   - Cell adjacency model.
   - Neighbor load and handover target scoring.
3. `smart_labeler.py`
   - Rule-based SON labels used for training.
4. `stability_controller.py`
   - Cooldown/hysteresis/action anti-oscillation.
5. `action_validator.py`
   - Final rule constraints before action execution.
6. `model_updater.py`
   - Optional continuous retraining monitor.

### Dashboard
File: `dashboard/app.py`

Responsibilities:
1. Render real-time KPI tiles and KPI graphs.
2. Show explicit load-balancing graph (score + imbalance).
3. Show AI decision log with proposed/final actions.
4. Send operator controls:
   - Error injection.
   - eNB start/stop.
   - `AI Action` (start all eNB + trigger rebalance).

## 3. Data and Feature Flow

### KPI Vector Format (AI Input)
Per interval, NS-3 sends 42 values:
- 7 metrics x 6 eNBs:
  - Throughput
  - Delay
  - Packet loss
  - UE count
  - RSRP
  - SINR
  - Cell load

### Model Feature Handling
1. Base features: 42.
2. Neighbor augmentation: +24 derived features (when applicable).
3. Inference path adapts to expected model dimensionality.

## 4. Action Semantics
Action IDs:
1. `0`: Balance
2. `1`: Increase power
3. `2`: Reduce power
4. `3`: Handover-oriented action

Execution constraints:
1. Disabled eNBs ignore AI actions.
2. Stability layer can override proposed actions.
3. Validator layer can further downgrade/replace risky actions.

## 5. Control Channels
1. `5000` AI socket
   - NS-3 -> AI: KPI vector
   - AI -> NS-3: action vector
2. `5001` Injection socket
   - Dashboard -> NS-3: runtime error injection command
3. `5002` eNB control socket
   - Dashboard -> NS-3: `START`, `STOP`, `REBALANCE`

## 6. Core Output Files
1. `../ns-3-dev/city_kpi_dataset.csv`
   - Primary KPI time-series output used by dashboard and model updates.
2. `ai_decisions.log`
   - Rich per-interval decision trace used by dashboard log panel.

## 7. Design Notes
1. eNB stop/start is modeled as controlled radio behavior, not physical node destruction.
2. Load balancing combines learned behavior with explicit policy constraints.
3. Stability and validation are mandatory post-processing stages before NS-3 action execution.
