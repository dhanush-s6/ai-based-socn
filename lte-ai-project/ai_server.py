"""
Enhanced AI Server for LTE-SON Cellular Network

Receives KPI data from NS3 simulator via socket, processes through hybrid AI model
(anomaly detection + trend prediction), and returns actions for each base station.
"""

import socket
import json
import sys
import threading
import numpy as np
import warnings
from pathlib import Path
from datetime import datetime
import logging

# Suppress warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ai_engine.hybrid_predictor import HybridPredictor
from ai_engine.stability_controller import StabilityController
from ai_engine.action_validator import ActionValidator
from ai_engine.model_updater import init_model_updater, get_model_updater
from config.config_manager import get_config
from simulator.error_injector import get_error_injector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AIServer")


class AIServer:
    """Extended AI Server with hybrid prediction capabilities."""
    
    def __init__(self):
        """Initialize AI server."""
        self.host = get_config("ai_engine.server_host", "127.0.0.1")
        self.port = get_config("ai_engine.server_port", 5000)
        self.model_path = get_config("ai_engine.hybrid_model_path", "models/network_ai_hybrid.pkl")
        
        # Initialize model
        self.model = HybridPredictor()
        self._load_or_train_model()
        
        # Initialize model updater for continuous learning
        self.model_updater = init_model_updater(self.model_path)

        # Decision stabilizer to prevent oscillation/handover spam
        self.stability_controller = StabilityController(num_cells=6)
        self.action_validator = ActionValidator()
        
        # Error injector for testing
        self.error_injector = get_error_injector()
        
        # Server socket
        self.server = None
        self.client_conn = None
        self.client_addr = None
        self.running = False
        
        # Statistics
        self.prediction_count = 0
        self.request_count = 0
        self.last_kpi_data = None
        self.last_decision = None
        self.decision_log_file = Path("ai_decisions.log")
        
        logger.info(f"AI Server initialized on {self.host}:{self.port}")
    
    def _load_or_train_model(self):
        """Load existing model or train from scratch."""
        model_path = Path(self.model_path)
        training_data = Path(get_config("data_pipeline.training_data_path", "training_dataset.csv"))
        
        logger.info(f"Model path configured: {model_path}")
        
        if model_path.exists():
            logger.info(f"Loading model from {model_path}")
            try:
                self.model = HybridPredictor()  # Create fresh instance
                self.model.load(str(model_path))
                logger.info(f"✓ Model loaded successfully")
                logger.info(f"  Features: {self.model.feature_names}")
                logger.info(f"  Trained: {self.model.is_trained}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                logger.info("Training new model instead...")
                self.model = HybridPredictor()
                if training_data.exists():
                    self.model.train(str(training_data))
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    self.model.save(str(model_path))
                else:
                    logger.warning(f"No training data at {training_data}")
        elif training_data.exists():
            logger.info(f"Training new model from {training_data}")
            self.model = HybridPredictor()
            self.model.train(str(training_data))
            model_path.parent.mkdir(parents=True, exist_ok=True)
            self.model.save(str(model_path))
        else:
            logger.warning("No model or training data found. Model will need to be trained separately.")
    
    def process_kpi_data(self, kpi_data: list) -> dict:
        """
        Process KPI data and generate predictions.
        
        Args:
            kpi_data: List of 42 KPI values (7 metrics × 6 towers)
        
        Returns:
            Dictionary with predictions and actions
        """
        self.request_count += 1
        
        try:
            if not self.model.is_trained:
                logger.warning("Model not trained, returning default actions")
                return self._get_default_response()
            
            # Validate input size (should be 42 features for 7 metrics × 6 cells)
            if len(kpi_data) != 42:
                logger.error(f"Invalid KPI data size: expected 42, got {len(kpi_data)}")
                logger.error(f"KPI data: {kpi_data}")
                return self._get_error_response(f"Invalid input size: {len(kpi_data)} (expected 42)")
            
            # Get predictions from hybrid model
            try:
                predictions = self.model.predict(kpi_data)
            except ValueError as ve:
                if "features" in str(ve).lower():
                    logger.error(f"Feature mismatch error: {ve}")
                    logger.error(f"This likely means the model expects different features than the simulator is sending.")
                    logger.error(f"Reloading model...")
                    self._load_or_train_model()
                    return self._get_error_response(f"Model feature mismatch, reloading. Error: {str(ve)[:100]}")
                raise
            
            # Extract proposed actions from model output
            proposed_actions = np.array(
                [cell_pred.get("action", 0) for cell_pred in predictions.get("cells", [])],
                dtype=int
            )

            # Ensure action vector always has exactly 6 elements
            if proposed_actions.size < 6:
                proposed_actions = np.pad(proposed_actions, (0, 6 - proposed_actions.size), constant_values=0)
            elif proposed_actions.size > 6:
                proposed_actions = proposed_actions[:6]

            # Build per-cell KPI map for stability controller (1-indexed cell IDs)
            current_kpi = self._build_cell_kpi_map(kpi_data)

            # Apply anti-oscillation/cooldown constraints
            sim_time = float(self.request_count)
            stabilized_actions, stability_info = self.stability_controller.apply_stability(
                proposed_actions=proposed_actions,
                current_kpi=current_kpi,
                timestamp_sec=sim_time
            )

            # Final safety validation before execution
            network_state = self._build_network_state(current_kpi)
            validated_actions, validation_report = self.action_validator.validate_all_actions(
                proposed_actions=stabilized_actions,
                current_kpis=current_kpi,
                network_state=network_state,
            )

            actions = [int(a) for a in validated_actions]

            # Enrich predictions with stability metadata for dashboard observability
            for idx, cell_pred in enumerate(predictions.get("cells", [])):
                cell_id_1 = idx + 1
                cell_info = stability_info.get(cell_id_1, {})
                cell_pred["proposed_action"] = int(proposed_actions[idx]) if idx < proposed_actions.size else 0
                cell_pred["action"] = int(stabilized_actions[idx]) if idx < stabilized_actions.size else 0
                cell_pred["stability_reason"] = cell_info.get("reason", "Accepted")
                cell_pred["stability_confidence"] = float(cell_info.get("confidence", 1.0))
                validation_info = validation_report.get(cell_id_1, {})
                cell_pred["validated_action"] = int(validation_info.get("final", cell_pred["action"]))
                cell_pred["validation_warnings"] = validation_info.get("warnings", [])

                # Ensure returned action matches the validated result.
                if idx < len(actions):
                    cell_pred["action"] = int(actions[idx])
            
            self.prediction_count += 1
            self.last_kpi_data = kpi_data
            self.last_decision = predictions  # Store latest decision
            
            # Log decision to file for dashboard to read
            self._log_decision(predictions)
            
            # Return JSON response
            response = {
                "status": "success",
                "actions": actions,
                "predictions": predictions,
                "request_id": self.request_count,
                "statistics": self.get_statistics()
            }
            
            return response
        
        except Exception as e:
            logger.error(f"Error processing KPI data: {e}")
            return self._get_error_response(str(e))

    def _build_cell_kpi_map(self, kpi_data: list) -> dict:
        """Convert flat 42 KPI features into per-cell mapping for stability checks."""
        cell_map = {}
        metrics_per_cell = 7

        for cell_id in range(1, 7):
            start = (cell_id - 1) * metrics_per_cell
            values = kpi_data[start:start + metrics_per_cell]
            if len(values) < metrics_per_cell:
                values = values + [0.0] * (metrics_per_cell - len(values))

            cell_map[cell_id] = {
                "throughput": float(values[0]),
                "delay": float(values[1]),
                "loss": float(values[2]),
                "packet_loss": float(values[2]),
                "ue_count": float(values[3]),
                "rsrp": float(values[4]),
                "sinr": float(values[5]),
                "load": float(values[6]),
                "cell_load": float(values[6]),
            }

        return cell_map

    def _build_network_state(self, current_kpi: dict) -> dict:
        """Build minimal network-wide state for action validation constraints."""
        loads = [float(v.get("cell_load", 0.0)) for v in current_kpi.values()]
        delays = [float(v.get("delay", 0.0)) for v in current_kpi.values()]

        return {
            "handover_rate_per_cell": 0.0,
            "cpu_usage": 0.5,
            "avg_temp_c": 60.0,
            "mean_load": float(np.mean(loads)) if loads else 0.0,
            "max_load": float(np.max(loads)) if loads else 0.0,
            "mean_delay": float(np.mean(delays)) if delays else 0.0,
        }
    
    def _get_default_response(self) -> dict:
        """Get default response (all balance actions)."""
        return {
            "status": "untrained",
            "actions": [0] * 6,  # All balance
            "predictions": {"cells": [{"cell_id": i, "action": 0} for i in range(6)]},
            "request_id": self.request_count
        }
    
    def _get_error_response(self, error_msg: str) -> dict:
        """Get error response."""
        return {
            "status": "error",
            "error": error_msg,
            "actions": [0] * 6,
            "request_id": self.request_count
        }
    
    def _log_decision(self, predictions: dict):
        """Log AI decision to file for dashboard to read."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "request_id": self.request_count,
                "overall_anomaly_score": predictions.get("overall_anomaly_score", 0),
                "overall_failure_probability": predictions.get("overall_failure_probability", 0),
                "cells": predictions.get("cells", [])
            }
            
            with open(self.decision_log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        
        except Exception as e:
            logger.warning(f"Failed to log decision: {e}")
    
    def get_statistics(self) -> dict:
        """Get server statistics."""
        return {
            "total_requests": self.request_count,
            "successful_predictions": self.prediction_count,
            "model_trained": self.model.is_trained,
            "model_version": self.model.model_version,
            "retraining_enabled": get_config("model_updater.enabled", True)
        }
    
    def handle_client(self):
        """Handle client connection and messaging."""
        logger.info(f"Client connected: {self.client_addr}")
        
        try:
            while self.running:
                # Receive KPI data from simulator
                data = self.client_conn.recv(4096)
                
                if not data:
                    logger.info("Client disconnected")
                    break
                
                try:
                    # Parse KPI data (comma-separated floats)
                    kpi_string = data.decode().strip()
                    kpi_data = list(map(float, kpi_string.split(",")))
                    
                    # Process and get predictions
                    response = self.process_kpi_data(kpi_data)
                    
                    # Send back actions as space-separated string
                    # Format: "action0 action1 action2 action3 action4 action5"
                    actions_str = " ".join(map(str, response["actions"]))
                    self.client_conn.send(actions_str.encode() + b'\n')
                    
                    if self.request_count % 100 == 0:
                        logger.info(f"Processed {self.request_count} predictions from simulator")
                
                except (ValueError, IndexError) as e:
                    logger.error(f"Invalid KPI data format: {e}")
                    self.client_conn.send(b"ERROR\n")
        
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        
        finally:
            self.client_conn.close()
    
    def start(self):
        """Start the AI server."""
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.running = True
            
            logger.info(f"✓ AI Server listening on {self.host}:{self.port}")
            logger.info("Waiting for NS3 simulator connection...")
            
            # Accept client connection
            self.client_conn, self.client_addr = self.server.accept()
            
            # Start model updater for continuous learning
            if get_config("model_updater.enabled", True):
                self.model_updater.start_continuous_monitoring()
                logger.info("Model updater started - continuous retraining enabled")
            
            # Handle client in main thread
            self.handle_client()
        
        except KeyboardInterrupt:
            logger.info("Shutting down AI server...")
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Gracefully shutdown the server."""
        self.running = False
        
        if self.model_updater:
            self.model_updater.stop_continuous_monitoring()
        
        if self.client_conn:
            self.client_conn.close()
        
        if self.server:
            self.server.close()
        
        logger.info("AI Server shut down")
        logger.info(f"Final Statistics: {self.get_statistics()}")


if __name__ == "__main__":
    server = AIServer()
    server.start()