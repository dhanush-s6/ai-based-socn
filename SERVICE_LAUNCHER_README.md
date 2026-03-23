# Service Launcher Utilities for LTE-AI-SON

This directory contains utilities to automatically start all services for the LTE-AI-SON project.

## 📋 Available Launchers

### 1. **Terminal Mode** (Recommended for Development)
Opens 3 separate terminal windows for each service:

```bash
# Using Python script
python3 start_all_services.py

# Or using bash wrapper
bash start_services.sh
```

**Advantages:**
- Easy to see output from each service
- Can interact with each terminal independently
- Easy to close individual services

**Services in separate terminals:**
- Terminal 1: AI Server (Port 5000)
- Terminal 2: Dashboard (Port 8050)
- Terminal 3: NS-3 Simulator

---

### 2. **Background Mode** (For Headless/CI Environments)
Runs all services as background processes with log files:

```bash
# Using Python script
python3 start_services_background.py

# Or using bash wrapper
bash start_services_bg.sh

# With custom parameters
python3 start_services_background.py --num-ue 100 --sim-time 300

# Without interactive monitoring
python3 start_services_background.py --no-monitor
```

**Advantages:**
- Runs in background without blocking terminal
- Provides interactive monitoring interface
- Logs saved to `service_logs/` directory
- Can restart individual services
- Better for automated deployments

**Command-line options:**
- `--num-ue N`: Number of UEs for simulation (default: 2000)
- `--sim-time N`: Simulation duration in seconds (default: 1800)
- `--no-monitor`: Don't show interactive monitor (just run in background)

---

## 🚀 Quick Start

### Option A: Terminal Mode (Easiest)
```bash
# From project root
bash start_services.sh
```

This will open 3 terminals automatically. Each terminal shows live output.

### Option B: Background Mode
```bash
# From project root
python3 start_services_background.py

# Interactive commands:
# - 'logs <service>': View logs (ai_server, dashboard, ns3)
# - 'status': Show service status
# - 'stop': Shutdown all services
# - 'restart <service>': Restart a service
# - 'q' or 'quit': Exit monitor
```

---

## 🔍 Accessing Services

Once running, access:

- **Dashboard Web UI**: Open browser to `http://127.0.0.1:8050`
- **AI Server**: Listening on `127.0.0.1:5000` (NS-3 communicates with this)
- **NS-3 Simulator**: Running simulation, sending KPI vectors

---

## 📊 Log Files

### Terminal Mode
- Output is shown directly in each terminal
- Closing a terminal closes that service

### Background Mode
- **AI Server Log**: `service_logs/ai_server.log`
- **Dashboard Log**: `service_logs/dashboard.log`
- **NS-3 Simulator Log**: `service_logs/ns3_simulator.log`
- **AI Decisions**: `lte-ai-project/ai_decisions.log`
- **KPI Dataset**: `ns-3-dev/city_kpi_dataset.csv`

---

## ⚙️ Prerequisites

Before running, ensure:

1. **Python virtual environment is set up:**
   ```bash
   cd lte-ai-project
   python3 -m venv env
   source env/bin/activate
   pip install -r requirements.txt
   ```

2. **NS-3 is built:**
   ```bash
   cd ns-3-dev
   ns3 build
   ```

3. **Terminal emulator installed (for Terminal Mode):**
   - gnome-terminal (GNOME)
   - xterm
   - tilix
   - konsole (KDE)
   - terminator

---

## 🛑 Stopping Services

### Terminal Mode
- Close each terminal window, or
- Press `Ctrl+C` in each terminal

### Background Mode
- Type `stop` in the monitor
- Or press `Ctrl+C`

---

## 🔧 Troubleshooting

### "Virtual environment not found"
Solution:
```bash
cd lte-ai-project
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### "NS-3 executable not found"
Solution:
```bash
cd ns-3-dev
ns3 build
```

### "No terminal emulator found" (Terminal Mode only)
The script will fall back to xterm. Install gnome-terminal or another emulator:
```bash
# Ubuntu/Debian
sudo apt-get install gnome-terminal

# Fedora
sudo dnf install gnome-terminal

# Arch
sudo pacman -S gnome-terminal
```

### Dashboard not accessible at http://127.0.0.1:8050
1. Check if dashboard is running: `logs dashboard`
2. Check firewall settings
3. Try: `http://localhost:8050`

### AI Server not responding
1. Check logs: `logs ai_server`
2. Verify port 5000 is not in use: `lsof -i :5000`
3. Check if virtual environment path is correct

---

## 📝 Environment Setup Reminder

Each time you start a new shell, the virtual environment might not be active.  The launchers automatically handle this by activating the venv before running services.

If running services manually:
```bash
cd lte-ai-project
source env/bin/activate
python3 ai_server.py
```

---

## 🎯 Typical Workflow

```bash
# Start all services
bash start_services.sh

# Dashboard opens in browser at http://127.0.0.1:8050

# Monitor KPIs and AI decisions live

# Use error injection, start/stop eNBs from dashboard controls

# When done:
# - Terminal Mode: Close each terminal
# - Background Mode: Type 'stop' in monitor
```

---

## 📚 For More Information

See the main project documentation:
- [README.md](../README.md) - Project overview
- [lte-ai-project/ARCHITECTURE.md](../lte-ai-project/ARCHITECTURE.md) - System architecture
- [lte-ai-project/INSTALLATION.md](../lte-ai-project/INSTALLATION.md) - Detailed installation steps
