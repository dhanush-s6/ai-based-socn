#!/bin/bash
# Reset simulation data for a fresh NS-3 run
# Keeps training_dataset.csv (persistent) but clears temporary KPI data

KPI_FILE="/home/darkdevil/Desktop/project/lte-ai-project/data/city_kpi_dataset.csv"

echo "Resetting simulation data..."

# Clear KPI data (NS-3 will overwrite on start)
rm -f "$KPI_FILE"
echo "✓ Cleared city_kpi_dataset.csv"

# Also remove any stale copy in ns-3-dev (from old config)
rm -f /home/darkdevil/Desktop/project/ns-3-dev/city_kpi_dataset.csv

# Keep training_dataset.csv untouched (persistent historical data)
echo "✓ Kept training_dataset.csv (persistent)"

# Clear AI decision logs
rm -f /home/darkdevil/Desktop/project/lte-ai-project/ai_decisions.log
echo "✓ Cleared AI decision logs"

echo ""
echo "✓ Simulation ready for fresh NS-3 run"
echo ""
echo "Run order:"
echo "  Terminal 1:  cd lte-ai-project && source env/bin/activate && python3 ai_server.py"
echo "  Terminal 2:  cd lte-ai-project && source env/bin/activate && python3 dashboard/app.py"
echo "  Terminal 3:  cd ns-3-dev && ./ns3 run 'lte_ai_simulator_2000ues --numUe=2000 --simTime=1800 --kpiInterval=1.0'"
