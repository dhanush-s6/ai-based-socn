#!/usr/bin/env python3
"""
Background Service Launcher for LTE-AI-SON Project
Runs AI Server, Dashboard, and NS-3 Simulator as background processes
(Alternative to terminal-based launcher)
"""

import subprocess
import sys
import os
import signal
import time
from pathlib import Path
from typing import List, Optional

# Project paths
PROJECT_ROOT = Path(__file__).parent
LTE_AI_PROJECT = PROJECT_ROOT / "lte-ai-project"
NS3_DEV = PROJECT_ROOT / "ns-3-dev"
VENV_PATH = LTE_AI_PROJECT / "env" / "bin" / "python3"
LOG_DIR = PROJECT_ROOT / "service_logs"

class BackgroundServiceLauncher:
    def __init__(self):
        self.processes: dict = {}
        self.log_dir = LOG_DIR
        self.log_dir.mkdir(exist_ok=True)
        
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
        
        if not (LTE_AI_PROJECT / "ai_server.py").exists():
            print(f"❌ AI server not found: {LTE_AI_PROJECT / 'ai_server.py'}")
            return False
        
        if not (LTE_AI_PROJECT / "dashboard" / "app.py").exists():
            print(f"❌ Dashboard app not found: {LTE_AI_PROJECT / 'dashboard' / 'app.py'}")
            return False
        
        print("✓ All paths validated")
        return True

    def start_ai_server(self) -> bool:
        """Start AI Server as background process"""
        log_file = self.log_dir / "ai_server.log"
        
        try:
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    [str(VENV_PATH), "-u", "ai_server.py"],
                    cwd=str(LTE_AI_PROJECT),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
            self.processes["AI Server"] = {
                "process": process,
                "log": log_file
            }
            print(f"✓ Started AI Server (PID: {process.pid})")
            print(f"  Log: {log_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to start AI Server: {e}")
            return False

    def start_dashboard(self) -> bool:
        """Start Dashboard as background process"""
        log_file = self.log_dir / "dashboard.log"
        
        try:
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    [str(VENV_PATH), "-u", "dashboard/app.py"],
                    cwd=str(LTE_AI_PROJECT),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
            self.processes["Dashboard"] = {
                "process": process,
                "log": log_file
            }
            print(f"✓ Started Dashboard (PID: {process.pid})")
            print(f"  Log: {log_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to start Dashboard: {e}")
            return False

    def start_ns3_simulator(self, num_ue: int = 2000, sim_time: int = 1800) -> bool:
        """Start NS-3 Simulator as background process"""
        log_file = self.log_dir / "ns3_simulator.log"
        
        try:
            ns3_cmd = f"lte_ai_simulator_2000ues --numUe={num_ue} --simTime={sim_time} --kpiInterval=1.0"
            
            # Check if ns3 command exists
            which_ns3 = subprocess.run(
                ["which", "ns3"],
                capture_output=True,
                timeout=2
            )
            
            if which_ns3.returncode != 0:
                ns3_bin = NS3_DEV / "ns3"
                if not ns3_bin.exists():
                    print(f"❌ NS-3 executable not found. Please build NS-3.")
                    return False
                ns3_path = str(ns3_bin)
            else:
                ns3_path = "ns3"
            
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    [ns3_path, "run", ns3_cmd],
                    cwd=str(NS3_DEV),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
            self.processes["NS-3 Simulator"] = {
                "process": process,
                "log": log_file
            }
            print(f"✓ Started NS-3 Simulator (PID: {process.pid})")
            print(f"  Log: {log_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to start NS-3 Simulator: {e}")
            return False

    def monitor_processes(self):
        """Monitor running processes and display status"""
        print("\n" + "="*60)
        print("Process Monitor")
        print("="*60)
        
        while True:
            print("\n📊 Running Services:")
            for service_name, info in self.processes.items():
                process = info["process"]
                status = "🟢 Running" if process.poll() is None else "🔴 Stopped"
                print(f"  {status}  {service_name} (PID: {process.pid})")
            
            print("\n📋 Available commands:")
            print("  - 'logs <service>': View logs (ai_server, dashboard, ns3)")
            print("  - 'status': Show this status")
            print("  - 'stop': Stop all services")
            print("  - 'restart <service>': Restart a service")
            print("  - 'q' or 'quit': Quit monitoring\n")
            
            user_input = input("Command> ").strip().lower()
            
            if user_input in ['q', 'quit']:
                break
            elif user_input == 'status':
                continue
            elif user_input.startswith('logs '):
                service = user_input.split(' ', 1)[1]
                self._show_logs(service)
            elif user_input == 'stop':
                break
            elif user_input.startswith('restart '):
                service = user_input.split(' ', 1)[1]
                self._restart_service(service)
            else:
                print("Unknown command")

    def _show_logs(self, service: str):
        """Show logs for a service"""
        service_map = {
            'ai_server': 'AI Server',
            'dashboard': 'Dashboard',
            'ns3': 'NS-3 Simulator'
        }
        
        full_service_name = service_map.get(service)
        if not full_service_name:
            print(f"Unknown service: {service}")
            return
        
        if full_service_name not in self.processes:
            print(f"Service not running: {full_service_name}")
            return
        
        log_file = self.processes[full_service_name]["log"]
        if log_file.exists():
            print(f"\n--- Logs for {full_service_name} (last 50 lines) ---")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-50:]:
                    print(line, end='')
            print(f"\n--- End of logs ---\n")
        else:
            print(f"Log file not found: {log_file}")

    def _restart_service(self, service: str):
        """Restart a specific service"""
        service_map = {
            'ai_server': 'AI Server',
            'dashboard': 'Dashboard',
            'ns3': 'NS-3 Simulator'
        }
        
        full_service_name = service_map.get(service)
        if not full_service_name:
            print(f"Unknown service: {service}")
            return
        
        if full_service_name not in self.processes:
            print(f"Service not running: {full_service_name}")
            return
        
        print(f"Restarting {full_service_name}...")
        self._stop_service(full_service_name)
        time.sleep(2)
        
        if full_service_name == "AI Server":
            self.start_ai_server()
        elif full_service_name == "Dashboard":
            self.start_dashboard()
        elif full_service_name == "NS-3 Simulator":
            self.start_ns3_simulator()

    def start_all(self, num_ue: int = 2000, sim_time: int = 1800) -> bool:
        """Start all services"""
        print("\n" + "="*60)
        print("LTE-AI-SON Background Service Launcher")
        print("="*60 + "\n")
        
        if not self._validate_paths():
            return False
        
        print("\n🚀 Starting all services...\n")
        
        print("1️⃣  Launching AI Server...")
        if not self.start_ai_server():
            return False
        time.sleep(2)
        
        print("\n2️⃣  Launching Dashboard...")
        if not self.start_dashboard():
            return False
        time.sleep(2)
        
        print("\n3️⃣  Launching NS-3 Simulator...")
        if not self.start_ns3_simulator(num_ue, sim_time):
            return False
        
        print("\n" + "="*60)
        print("✅ All services launched!")
        print("="*60)
        print("\nService Details:")
        print("  • AI Server: Listening on 127.0.0.1:5000")
        print("  • Dashboard: Available at http://127.0.0.1:8050")
        print("  • NS-3 Simulator: Sending KPI vectors to AI Server")
        print(f"\nLog Directory: {self.log_dir}")
        print("Logs:")
        print(f"  • AI Server: {self.log_dir}/ai_server.log")
        print(f"  • Dashboard: {self.log_dir}/dashboard.log")
        print(f"  • NS-3 Simulator: {self.log_dir}/ns3_simulator.log")
        print(f"  • AI Decisions: {LTE_AI_PROJECT}/ai_decisions.log")
        print(f"  • KPI Dataset: {NS3_DEV}/city_kpi_dataset.csv")
        print("\n⏹️  Type 'stop' or Ctrl+C to shutdown")
        print("="*60 + "\n")
        
        return True

    def _stop_service(self, service_name: str):
        """Stop a specific service"""
        if service_name not in self.processes:
            return
        
        info = self.processes[service_name]
        process = info["process"]
        
        try:
            process.terminate()
            process.wait(timeout=5)
            print(f"  ✓ Stopped {service_name}")
        except subprocess.TimeoutExpired:
            process.kill()
            print(f"  ⚠ Killed {service_name}")
        except Exception as e:
            print(f"  ⚠ Error stopping {service_name}: {e}")

    def cleanup(self, signum=None, frame=None):
        """Handle graceful shutdown"""
        print("\n\n🛑 Shutting down all services...")
        for service_name in list(self.processes.keys()):
            self._stop_service(service_name)
        
        print("✅ Cleanup complete")
        sys.exit(0)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Launch LTE-AI-SON services in background"
    )
    parser.add_argument(
        '--num-ue',
        type=int,
        default=2000,
        help='Number of UEs for NS-3 simulation (default: 2000)'
    )
    parser.add_argument(
        '--sim-time',
        type=int,
        default=1800,
        help='Simulation time in seconds (default: 1800)'
    )
    parser.add_argument(
        '--no-monitor',
        action='store_true',
        help='Do not show monitoring interface'
    )
    
    args = parser.parse_args()
    
    launcher = BackgroundServiceLauncher()
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, launcher.cleanup)
    signal.signal(signal.SIGTERM, launcher.cleanup)
    
    # Start all services
    success = launcher.start_all(args.num_ue, args.sim_time)
    
    if success:
        if not args.no_monitor:
            try:
                launcher.monitor_processes()
            except KeyboardInterrupt:
                pass
        else:
            # Keep running without interactive monitoring
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        
        launcher.cleanup()
    else:
        print("\n❌ Failed to start services")
        sys.exit(1)

if __name__ == "__main__":
    main()
