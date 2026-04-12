#!/usr/bin/env python3
"""
AI Model Training Script

Generates a training dataset using NS3 simulator, then trains the hybrid AI model
with error-aware augmentation.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_engine.hybrid_predictor import HybridPredictor
from config.config_manager import get_config
from training.error_data_generator import generate_error_aware_training_data

def run_dataset_generator(num_ues=500, sim_time=600):
    """Run NS3 dataset generator to create training data."""
    print("\n" + "="*60)
    print("STEP 1: Generating Training Dataset")
    print("="*60)
    
    os.chdir("/home/darkdevil/Desktop/project/ns-3-dev")
    
    cmd = f'./ns3 run "lte_ai_dataset_generator --numUe={num_ues} --simTime={sim_time}"'
    
    print(f"Running: {cmd}")
    print("This may take several minutes...")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error running dataset generator!")
        print(f"STDERR: {result.stderr}")
        return False
    
    print(result.stdout)
    print("✓ Dataset generation completed")
    
    # Verify dataset was created
    dataset_path = Path("/home/darkdevil/Desktop/project/lte-ai-project/data/training_dataset.csv")
    if not dataset_path.exists():
        print(f"❌ Dataset file not found at {dataset_path}")
        return False
    
    print(f"✓ Dataset saved to: {dataset_path}")
    
    # Check row count
    with open(dataset_path) as f:
        rows = len(f.readlines()) - 1  # Exclude header
    print(f"✓ Dataset contains {rows} samples")
    
    return True

def augment_with_errors(dataset_path):
    """**NEW**: Augment training data with error scenarios for better AI training."""
    print("\n" + "="*60)
    print("STEP 1.5: Augmenting Data with Error Scenarios")
    print("="*60)
    
    try:
        print("\n[ERROR-AWARE TRAINING]")
        print("The AI model needs to learn patterns from error scenarios.")
        print("Augmenting training data with 8 QoS degradation factors...\n")
        
        # Augment dataset with error-injected samples
        augmented_path = generate_error_aware_training_data(
            str(dataset_path),
            str(dataset_path),  # Overwrite original
            multiplier=0.5  # Add 50% more samples with errors
        )
        
        print(f"✓ Data augmentation complete!")
        return True
    
    except Exception as e:
        print(f"⚠ Note: Error augmentation failed ({str(e)})")
        print(f"  Training will proceed with original data only.")
        print(f"  This means the model may not learn error responses well.")
        return False

def train_model(dataset_path):
    """Train the hybrid AI model on the generated dataset."""
    print("\n" + "="*60)
    print("STEP 2: Training AI Model")
    print("="*60)
    
    try:
        print(f"Loading dataset from: {dataset_path}")
        
        # Load and check dataset
        import pandas as pd
        df = pd.read_csv(dataset_path)
        print(f"Dataset shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        
        # Check if error augmentation was applied
        if '_error_type' in df.columns:
            error_count = df['_error_type'].notna().sum()
            print(f"✓ Error-augmented samples detected: {error_count}")
        else:
            print(f"⚠ No error-augmented samples in dataset")
            print(f"  Consider running error augmentation for better model training")
        
        # Create and train model
        print("\nInitializing hybrid predictor...")
        model = HybridPredictor()
        
        print(f"Training on {len(df)} samples...")
        model.train(dataset_path, test_size=0.2)
        
        # Save trained model
        model_path = Path(get_config("ai_engine.hybrid_model_path", "models/network_ai_hybrid.pkl"))
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Saving model to: {model_path}")
        model.save(str(model_path))
        
        print("✓ Model training completed successfully!")
        print(f"✓ Model saved to: {model_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during training: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_model():
    """Verify the trained model can make predictions."""
    print("\n" + "="*60)
    print("STEP 3: Verifying Model")
    print("="*60)
    
    try:
        model = HybridPredictor()
        model_path = Path(get_config("ai_engine.hybrid_model_path", "models/network_ai_hybrid.pkl"))
        
        if not model_path.exists():
            print(f"❌ Model file not found at {model_path}")
            return False
        
        print(f"Loading model from: {model_path}")
        model.load(str(model_path))
        
        # Test prediction on random data
        import numpy as np
        test_data = np.random.rand(42)  # 7 features × 6 cells
        
        print("Testing prediction...")
        result = model.predict(test_data)
        
        print(f"✓ Prediction successful!")
        print(f"  Anomaly scores: {result.get('anomaly_scores', 'N/A')}")
        print(f"  Risk probabilities: {result.get('risk_probabilities', 'N/A')}")
        print(f"  Recommended actions: {result.get('recommended_actions', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main training pipeline."""
    os.chdir("/home/darkdevil/Desktop/project/lte-ai-project")
    
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║      LTE AI Model Training Pipeline                      ║")
    print("║  Generate Dataset → Train Model → Verify                 ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    # Dataset parameters
    num_ues = 500      # Start with 500 UEs for faster generation
    sim_time = 600     # 10 minutes of data
    
    print(f"Configuration:")
    print(f"  • UEs: {num_ues}")
    print(f"  • Simulation Time: {sim_time}s")
    print(f"  • Dataset Path: /home/darkdevil/Desktop/project/lte-ai-project/data/training_dataset.csv")
    print(f"  • Model Path: {get_config('ai_engine.hybrid_model_path', 'models/network_ai_hybrid.pkl')}")
    
    start_time = time.time()
    
    # Step 1: Generate dataset
    if not run_dataset_generator(num_ues, sim_time):
        print("\n❌ Failed to generate dataset")
        sys.exit(1)
    
    # Step 1.5: **NEW** Augment with error scenarios
    dataset_path = "/home/darkdevil/Desktop/project/lte-ai-project/data/training_dataset.csv"
    augment_with_errors(dataset_path)  # Non-fatal if fails
    
    # Step 2: Train model (now with error-augmented data)
    if not train_model(dataset_path):
        print("\n❌ Failed to train model")
        sys.exit(1)
    
    # Step 3: Verify model
    if not verify_model():
        print("\n❌ Failed to verify model")
        sys.exit(1)
    
    elapsed = time.time() - start_time
    
    print("\n" + "="*60)
    print("✓ TRAINING PIPELINE COMPLETED SUCCESSFULLY")
    print("="*60)
    print(f"Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print("\nYou can now:")
    print("  1. Run the simulator: python3 ai_server.py")
    print("  2. Run the dashboard: python3 dashboard/app.py")
    print("  3. Start NS3: ./ns3 run 'lte_ai_simulator_2000ues'")

if __name__ == "__main__":
    main()
