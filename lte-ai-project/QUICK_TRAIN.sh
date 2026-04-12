#!/bin/bash
# Quick Training & Testing Commands
# Copy and paste these commands to get everything set up

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   LTE-AI Model Retraining & Testing Commands              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Build NS3 with new dataset generator
echo "STEP 1: Build NS3 Dataset Generator"
echo "=================================="
echo "cd /home/darkdevil/Desktop/project/ns-3-dev"
echo "./ns3 configure && ./ns3 build"
echo ""

# Step 2: Generate training dataset
echo "STEP 2: Generate Training Dataset"
echo "================================="
echo "cd /home/darkdevil/Desktop/project/ns-3-dev"
echo "./ns3 run \"lte_ai_dataset_generator --numUe=500 --simTime=600\""
echo ""

# Step 3: Train AI Model
echo "STEP 3: Train AI Model"
echo "====================="
echo "cd /home/darkdevil/Desktop/project/lte-ai-project"
echo "source env/bin/activate"
echo "python3 train_model.py"
echo ""

# Step 4: Run the full system
echo "STEP 4: Run Full System (3 Terminals)"
echo "======================================"
echo ""
echo "Terminal 1 - AI Server:"
echo "  cd /home/darkdevil/Desktop/project/lte-ai-project"
echo "  source env/bin/activate"
echo "  python3 ai_server.py"
echo ""
echo "Terminal 2 - Dashboard:"
echo "  cd /home/darkdevil/Desktop/project/lte-ai-project"
echo "  source env/bin/activate"
echo "  python3 dashboard/app.py"
echo ""
echo "Terminal 3 - NS3 Simulator:"
echo "  cd /home/darkdevil/Desktop/project/ns-3-dev"
echo "  ./ns3 run \"lte_ai_simulator_2000ues --numUe=2000 --simTime=1800 --kpiInterval=1.0\""
echo ""

# Quick one-liner for everything (if feeling brave)
echo "QUICK ONE-LINER (Run all steps):"
echo "==============================="
echo "cd /home/darkdevil/Desktop/project/ns-3-dev && \\"
echo "./ns3 configure && ./ns3 build && \\"
echo "./ns3 run \"lte_ai_dataset_generator --numUe=500 --simTime=600\" && \\"
echo "cd /home/darkdevil/Desktop/project/lte-ai-project && \\"
echo "source env/bin/activate && \\"
echo "python3 train_model.py"
echo ""

# Verification commands
echo "VERIFICATION COMMANDS:"
echo "====================="
echo "# Check dataset was generated:"
echo "ls -lh /home/darkdevil/Desktop/project/lte-ai-project/data/"
echo "head /home/darkdevil/Desktop/project/lte-ai-project/data/training_dataset.csv"
echo ""
echo "# Check model was trained:"
echo "ls -lh /home/darkdevil/Desktop/project/lte-ai-project/models/"
echo ""
echo "# Test model:"
echo "python3 -c \"from ai_engine.hybrid_predictor import HybridPredictor; import numpy as np; m = HybridPredictor(); m.load('models/network_ai_hybrid.pkl'); r = m.predict(np.random.rand(42)); print('✓ Model works!')\""
echo ""

echo "✓ Commands ready to use!"
