#!/usr/bin/env python3
"""
Automated Service Launcher for LTE-AI-SON Project
Starts AI Server, Dashboard, and NS-3 Simulator in separate terminals
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path
from typing import List, Dict

# Project paths
PROJECT_ROOT = Path(__file__).parent
LTE_AI_PROJECT = PROJECT_ROOT / "lte-ai-project"
NS3_DEV = PROJECT_ROOT / "ns-3-dev"
VENV_PATH = LTE_AI_PROJECT / "env" / "bin" / "activate"

# Terminal emulator options (in priority order)
TERMINAL_EMULATORS = [
    ("gnome-terminal", ["gnome-terminal", "--", "bash", "-c"]),
    ("xterm", ["xterm", "-e"]),
    ("tilix", ["tilix", "-e"]),
    ("konsole", ["konsole", "-e"]),
    ("terminator", ["terminator", "-e"]),
]

class ServiceLauncher:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.terminal_cmd = self._find_terminal()
        
    def _find_terminal(self) -> List[str]:
        """Find the first available terminal emulator"""
        for name, cmd in TERMINAL_EMULATORS:
            try:
                result = subprocess.run(
                    ["which", name],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    print(f"✓ Found terminal emulator: {name}")
                    return cmd
            except Exception:
                continue
        
        print("⚠ No terminal emulator found. Using xterm as fallback.")
        return ["xterm", "-e"]

    def _validate_paths(self) -> bool:
        """Validate that all required paths exist"""
        if not PROJECT_ROOT.exists():
            print(f"❌ Project root not found: {PROJECT_ROOT}")
            return False
        
        if not LTE_AI_PROJECT.exists():
            print(f"❌ LTE AI project not found: {LTE_AI_PROJECT}")
            return False
        
        if not NS3_DEV.exists():
            print(f"❌ NS-3 dev not found: {NS3_DEV}")
            return False
        
        if not VENV_PATH.exists():
            print(f"❌ Virtual environment not found: {VENV_PATH}")
            print("   Run: cd lte-ai-project && python3 -m venv env && source env/bin/activate && pip install -r requirements.txt")
            return False
        
        # Check if ai_server.py exists
        if not (LTE_AI_PROJECT / "ai_server.py").exists():
            print(f"❌ AI server not found: {LTE_AI_PROJECT / 'ai_server.py'}")
            return False
        
        # Check if dashboard app.py exists
        if not (LTE_AI_PROJECT / "dashboard" / "app.py").exists():
            print(f"❌ Dashboard app not found: {LTE_AI_PROJECT / 'dashboard' / 'app.py'}")
            return False
        
        print("✓ All paths validated")
        return True

    def _check_ns3_build(self) -> bool:
        """Check if NS-3 is built"""
        ns3_build = NS3_DEV / "build"
        if not ns3_build.exists():
            print(f"⚠ NS-3 build not found at {ns3_build}")
            print("  You may need to run: cd ns-3-dev && ns3 build")
            response = input("Continue anyway? (y/n): ").strip().lower()
            return response == 'y'
        print("✓ NS-3 build found")
        return True

    def _create_command(self, service_type: str) -> str:
        """Create shell command for each service"""
        if service_type == "ai_server":
            return (
                f"cd {LTE_AI_PROJECT} && "
                f"source {VENV_PATH} && "
                f"echo '=== Starting AI Server ===' && "
                f"python3 ai_server.py"
            )
        
        elif service_type == "dashboard":
            return (
                f"cd {LTE_AI_PROJECT} && "
                f"source {VENV_PATH} && "
                f"echo '=== Starting Dashboard ===' && "
                f"echo 'Dashboard will be available at http://127.0.0.1:8050' && "
                f"python3 dashboard/app.py"
            )
        
        elif service_type == "ns3":
            return (
                f"cd {NS3_DEV} && "
                f"echo '=== Starting NS-3 Simulator ===' && "
                f"ns3 run 'lte_ai_simulator_2000ues --numUe=2000 --simTime=1800 --kpiInterval=1.0'"
            )
        
        return ""

    def start_service(self, service_name: str, service_type: str) -> bool:
        """Start a single service in a new terminal"""
        cmd = self._create_command(service_type)
        
        if not cmd:
            print(f"❌ Unknown service type: {service_type}")
            return False
        
        # Add a prompt at the end so terminal stays open after execution
        cmd += " && echo '\\n--- Service stopped. Press Enter to close ---' && read"
        
        try:
            full_cmd = self.terminal_cmd + [cmd]
            process = subprocess.Popen(full_cmd)
            self.processes[service_name] = process
            print(f"✓ Started {service_name} (PID: {process.pid})")
            return True
        except Exception as e:
            print(f"❌ Failed to start {service_name}: {e}")
            return False

    def start_all(self):
        """Start all services"""
        print("\n" + "="*60)
        print("LTE-AI-SON Service Launcher")
        print("="*60 + "\n")
        
        # Validate paths
        if not self._validate_paths():
            return False
        
        # Check NS-3 build
        if not self._check_ns3_build():
            return False
        
        print("\n🚀 Starting all services...\n")
        
        # Start AI Server
        print("1️⃣  Launching AI Server...")
        time.sleep(1)
        if not self.start_service("AI Server", "ai_server"):
            return False
        
        time.sleep(2)
        
        # Start Dashboard
        print("2️⃣  Launching Dashboard...")
        time.sleep(1)
        if not self.start_service("Dashboard", "dashboard"):
            return False
        
        time.sleep(2)
        
        # Start NS-3 Simulator
        print("3️⃣  Launching NS-3 Simulator...")
        time.sleep(1)
        if not self.start_service("NS-3 Simulator", "ns3"):
            return False
        
        print("\n" + "="*60)
        print("✅ All services launched!")
        print("="*60)
        print("\nService Details:")
        print("  • AI Server: Listening on 127.0.0.1:5000")
        print("  • Dashboard: Available at http://127.0.0.1:8050")
        print("  • NS-3 Simulator: Sending KPI vectors to AI Server")
        print("\nLogs:")
        print(f"  • AI Decisions: {LTE_AI_PROJECT}/ai_decisions.log")
        print(f"  • KPI Dataset: {NS3_DEV}/city_kpi_dataset.csv")
        print("\n⏹️  To stop all services: Press Ctrl+C (or close terminals)")
        print("="*60 + "\n")
        
        return True

    def cleanup(self, signum=None, frame=None):
        """Handle graceful shutdown"""
        print("\n\n🛑 Shutting down services...")
        for service_name, process in self.processes.items():
            try:
                process.terminate()
                print(f"  ✓ Terminated {service_name} (PID: {process.pid})")
            except Exception as e:
                print(f"  ⚠ Error terminating {service_name}: {e}")
        
        print("✅ Cleanup complete")
        sys.exit(0)

def main():
    launcher = ServiceLauncher()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, launcher.cleanup)
    signal.signal(signal.SIGTERM, launcher.cleanup)
    
    # Start all services
    success = launcher.start_all()
    
    if success:
        # Keep the main process alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            launcher.cleanup()
    else:
        print("\n❌ Failed to start services")
        sys.exit(1)

if __name__ == "__main__":
    main()
