#!/bin/bash

# LTE-AI SON System Setup Script
# For Ubuntu 24.04 LTS
# Usage: bash setup.sh

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════"
echo "  LTE-AI SON Cellular Network System Setup"
echo "  Ubuntu 24.04 LTS"
echo "════════════════════════════════════════════════════════════"
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/env"

# Check if running on Ubuntu
if [ ! -f /etc/os-release ]; then
    echo "❌ Could not detect OS"
    exit 1
fi

source /etc/os-release
if [[ ! "$PRETTY_NAME" =~ Ubuntu ]]; then
    echo "⚠️  Warning: This script is optimized for Ubuntu. You are running: $PRETTY_NAME"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 1: System dependencies
echo "📦 Step 1: Installing system dependencies..."
if ! command -v python3.12 &> /dev/null; then
    echo "   Installing Python 3.12..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev build-essential
    echo "   ✓ Python 3.12 installed"
else
    echo "   ✓ Python 3.12 already installed"
fi

# Step 2: Create virtual environment
echo ""
echo "🐍 Step 2: Creating virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3.12 -m venv "$VENV_DIR"
    echo "   ✓ Virtual environment created at $VENV_DIR"
else
    echo "   ✓ Virtual environment already exists"
fi

# Step 3: Activate and upgrade pip
echo ""
echo "📥 Step 3: Upgrading pip and installing packages..."
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel -q
echo "   ✓ Pip upgraded"

# Step 4: Install requirements
echo ""
echo "📚 Step 4: Installing Python dependencies (this may take a few minutes)..."
pip install -q -r "$PROJECT_DIR/requirements.txt" 2>/dev/null || {
    echo "   ⚠️  Some packages may have failed. Continuing..."
}
echo "   ✓ Python packages installed"

# Step 5: Create required directories
echo ""
echo "📁 Step 5: Creating required directories..."
mkdir -p "$PROJECT_DIR/models/backups"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/dataset"
echo "   ✓ Directories created"

# Step 6: Verify installation
echo ""
echo "✅ Step 6: Verifying installation..."
python -c "
import sys
packages = ['numpy', 'pandas', 'sklearn', 'flask', 'dash', 'yaml']
missing = []
for pkg in packages:
    try:
        __import__(pkg.replace('-', '_'))
    except ImportError:
        missing.append(pkg)

if missing:
    print(f'   ⚠️  Missing packages: {missing}')
    sys.exit(1)
else:
    print('   ✓ All core packages verified')
" || true

# Step 7: Create activation script
echo ""
echo "🚀 Step 7: Creating activation helpers..."

# Create activate script for easy future activation
cat > "$PROJECT_DIR/activate.sh" << 'EOF'
#!/bin/bash
source "$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")/env/bin/activate"
echo "✓ Virtual environment activated"
echo "Run 'python ai_server.py' to start AI server"
echo "Run 'python -m dashboard.app' to start dashboard"
EOF

chmod +x "$PROJECT_DIR/activate.sh"
echo "   ✓ Created activate.sh"

# Create quick-start script
cat > "$PROJECT_DIR/start_services.sh" << 'EOF'
#!/bin/bash

echo "Starting LTE-AI SON Services..."
echo ""
echo "Make sure you have 3 terminals open:"
echo "  Terminal 1: AI Server"
echo "  Terminal 2: Dashboard"  
echo "  Terminal 3: NS-3 Simulator"
echo ""
echo "In Terminal 1, run:"
echo "  source activate.sh && python ai_server.py"
echo ""
echo "In Terminal 2, run:"
echo "  source activate.sh && python -m dashboard.app"
echo ""
echo "In Terminal 3, run:"
echo "  cd ~/Desktop/ns-3-dev"
echo "  ./waf --run 'scratch/improved_simulator --numUes=2000'"
echo ""
EOF

chmod +x "$PROJECT_DIR/start_services.sh"
echo "   ✓ Created start_services.sh"

# Summary
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Setup Complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📌 Next Steps:"
echo ""
echo "1. Activate virtual environment:"
echo "   source $PROJECT_DIR/activate.sh"
echo ""
echo "2. Start the system (in 3 separate terminals):"
echo ""
echo "   Terminal 1 (AI Server):"
echo "   source $PROJECT_DIR/activate.sh"
echo "   python $PROJECT_DIR/ai_server.py"
echo ""
echo "   Terminal 2 (Dashboard):"
echo "   source $PROJECT_DIR/activate.sh"
echo "   python -m $PROJECT_DIR/dashboard.app"
echo ""
echo "   Terminal 3 (NS-3 Simulator - if you have NS-3 installed):"
echo "   cd ~/Desktop/ns-3-dev"
echo "   ./waf --run 'scratch/improved_simulator --numUes=2000'"
echo ""
echo "3. Open browser to: http://127.0.0.1:8050"
echo ""
echo "📖 For more info, see README.md"
echo ""
