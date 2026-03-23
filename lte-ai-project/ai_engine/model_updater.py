import time
import threading
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
import joblib
from ai_engine.hybrid_predictor import HybridPredictor
from config.config_manager import get_config


class ModelUpdater:
    """
    Continuous model retraining system.
    
    Monitors the training CSV for new data and automatically retrains the model
    when a threshold number of new samples are collected.
    """
    
    def __init__(self, model_path: str = None):
        """
        Initialize the model updater.
        
        Args:
            model_path: Path to the initial model (if None, will train from scratch)
        """
        self.model_path = model_path or get_config("ai_engine.hybrid_model_path")
        self.training_data_path = get_config("data_pipeline.training_data_path")
        self.retraining_interval = get_config("model_updater.retraining_interval", 100)
        self.min_accuracy = get_config("model_updater.min_accuracy", 0.75)
        self.backup_dir = Path(get_config("model_updater.model_backup_dir", "models/backups/"))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_model = HybridPredictor()
        self.last_row_count = 0
        self.is_training = False
        self.retraining_thread = None
        self.should_stop = False
        
        # Try to load existing model
        if Path(self.model_path).exists():
            self.current_model.load(self.model_path)
            print(f"✓ Loaded existing model from {self.model_path}")
        else:
            print(f"No existing model found at {self.model_path}")
    
    def get_current_row_count(self) -> int:
        """Get the number of rows in training data."""
        try:
            if not Path(self.training_data_path).exists():
                return 0
            df = pd.read_csv(self.training_data_path)
            return len(df)
        except Exception as e:
            print(f"Error reading training data: {e}")
            return 0
    
    def should_retrain(self) -> bool:
        """Check if retraining should be triggered."""
        current_rows = self.get_current_row_count()
        rows_new = current_rows - self.last_row_count
        
        if rows_new >= self.retraining_interval:
            print(f"[ModelUpdater] Retraining triggered: {rows_new} new samples collected")
            return True
        
        return False
    
    def retrain_model(self):
        """Retrain the model in background."""
        if self.is_training:
            print("[ModelUpdater] Model already training, skipping...")
            return
        
        if not Path(self.training_data_path).exists():
            print(f"[ModelUpdater] Training data not found: {self.training_data_path}")
            return
        
        self.is_training = True
        
        try:
            print("\n" + "="*60)
            print("[ModelUpdater] Starting model retraining...")
            print("="*60)
            
            start_time = datetime.now()
            
            # Create new model and train
            new_model = HybridPredictor()
            
            try:
                new_model.train(self.training_data_path)
            except Exception as train_error:
                error_msg = str(train_error)
                if "y contains 1 class" in error_msg or "minimum of 2 classes" in error_msg:
                    print(f"[ModelUpdater] ⚠ Warning: Insufficient data diversity for training")
                    print(f"[ModelUpdater] Details: {error_msg}")
                    print(f"[ModelUpdater] Keeping current model, will retry when more data is available")
                    self.is_training = False
                    return
                else:
                    raise
            
            # Save backup of old model
            if Path(self.model_path).exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.backup_dir / f"model_backup_{timestamp}.pkl"
                import shutil
                shutil.copy(self.model_path, backup_path)
                print(f"✓ Old model backed up to {backup_path}")
            
            # Replace current model
            old_model = self.current_model
            self.current_model = new_model
            self.current_model.save(self.model_path)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            self.last_row_count = self.get_current_row_count()
            
            print(f"✓ Retraining completed in {elapsed:.2f}s")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"[ModelUpdater] ERROR during retraining: {e}")
            self.is_training = False
            raise
        
        self.is_training = False
    
    def start_continuous_monitoring(self):
        """Start continuous monitoring in a background thread."""
        if self.retraining_thread is not None and self.retraining_thread.is_alive():
            print("[ModelUpdater] Monitoring already running")
            return
        
        self.should_stop = False
        self.retraining_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=False
        )
        self.retraining_thread.start()
        print("[ModelUpdater] Continuous monitoring started")
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        check_interval = 10  # Check every 10 seconds
        
        while not self.should_stop:
            try:
                if not self.is_training and self.should_retrain():
                    self.retrain_model()
                
                time.sleep(check_interval)
            
            except Exception as e:
                error_msg = str(e)
                if "y contains 1 class" in error_msg or "minimum of 2 classes" in error_msg:
                    print(f"[ModelUpdater] ⚠ Warning: Not enough class diversity yet ({error_msg[:50]}...)")
                    print(f"[ModelUpdater] Will continue collecting data. Retrying in {check_interval}s...")
                else:
                    print(f"[ModelUpdater] Error in monitoring loop: {e}")
                time.sleep(check_interval)
    
    def stop_continuous_monitoring(self):
        """Stop the continuous monitoring thread."""
        self.should_stop = True
        
        if self.retraining_thread and self.retraining_thread.is_alive():
            self.retraining_thread.join(timeout=5)
            print("[ModelUpdater] Continuous monitoring stopped")
    
    def get_model(self) -> HybridPredictor:
        """Get the current trained model."""
        return self.current_model
    
    def is_model_trained(self) -> bool:
        """Check if model is trained and ready."""
        return self.current_model.is_trained
    
    def get_status(self) -> dict:
        """Get status information."""
        return {
            "is_trained": self.current_model.is_trained,
            "is_currently_training": self.is_training,
            "total_rows": self.get_current_row_count(),
            "rows_since_last_training": self.get_current_row_count() - self.last_row_count,
            "retraining_interval": self.retraining_interval,
            "model_version": self.current_model.model_version
        }


# Singleton instance for global access
_updater_instance: Optional[ModelUpdater] = None


def init_model_updater(model_path: str = None) -> ModelUpdater:
    """Initialize the global model updater instance."""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = ModelUpdater(model_path)
    return _updater_instance


def get_model_updater() -> ModelUpdater:
    """Get the global model updater instance."""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = ModelUpdater()
    return _updater_instance


if __name__ == "__main__":
    # Example usage
    updater = ModelUpdater()
    
    # Start monitoring
    updater.start_continuous_monitoring()
    
    print("Model updater running. Press Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        updater.stop_continuous_monitoring()
