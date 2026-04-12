"""
Error-Aware Training Data Generator

Injects synthetic error scenarios into training data to teach the AI model
how to respond to each of the 8 QoS degradation factors.

This module integrates with the HybridPredictor to create labeled training
data where each sample includes:
- Raw KPI metrics
- Error type injected (if any)
- Optimal SON action to take
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.error_definitions import ErrorType, KPIImpactCalculator, ERROR_CATALOG
from simulator.error_injector import ErrorInjector
from ai_engine.smart_labeler import SmartLabeler, ErrorDetector


class ErrorDataGenerator:
    """
    Generates or augments training data with error scenarios.
    
    Strategy:
    1. Take existing training dataset(normal KPIs)
    2. For each sample, inject each error type
    3. Calculate optimal SON action using SmartLabeler
    4. Append error-augmented samples to training dataset
    """
    
    def __init__(self):
        """Initialize generator."""
        self.injector = ErrorInjector()
        self.labeler = SmartLabeler()
        self.error_detector = ErrorDetector()
        self.generated_samples = 0
    
    def augment_training_data(
        self,
        input_data_path: str,
        output_data_path: str = None,
        error_injection_multiplier: float = 1.0
    ) -> str:
        """
        Augment existing training data with error scenarios.
        
        Args:
            input_data_path: Path to original training CSV
            output_data_path: Path to save augmented dataset (if None, overwrites input)
            error_injection_multiplier: How many error variants to create per sample
                                       (e.g., 0.5 = add 50% more samples, 1.0 = double the dataset)
        
        Returns:
            Path to augmented dataset
        """
        print(f"\n{'='*70}")
        print("AUGMENTING TRAINING DATA WITH ERROR SCENARIOS")
        print(f"{'='*70}")
        
        if output_data_path is None:
            output_data_path = input_data_path
        
        # Load original data
        print(f"Loading original data from {input_data_path}...")
        df_original = pd.read_csv(input_data_path)
        print(f"Original dataset: {len(df_original)} samples")
        
        # Create augmented dataset
        augmented_data = []
        augmented_data.extend(df_original.to_dict('records'))  # Keep original
        
        # Calculate how many error samples to add
        num_error_samples = int(len(df_original) * error_injection_multiplier)
        
        print(f"Generating {num_error_samples} error-injected samples...")
        
        # For each error type
        error_types = list(ErrorType)[:-1]  # Exclude NONE
        errors_per_type = num_error_samples // len(error_types)
        
        for error_idx, error_type in enumerate(error_types):
            print(f"\n[{error_idx+1}/{len(error_types)}] Injecting {error_type.value}...")
            
            # Inject this error into random samples
            sample_indices = np.random.choice(len(df_original), min(errors_per_type, len(df_original)), replace=True)
            
            for sample_num, idx in enumerate(sample_indices):
                original_sample = df_original.iloc[idx].to_dict()
                
                # Extract KPI vector from sample (7 metrics × 6 cells = 42 values)
                kpi_vector = self._extract_kpi_vector(original_sample)
                
                # Inject error with random severity
                severity = np.random.uniform(
                    ERROR_CATALOG[error_type].severity_range[0],
                    ERROR_CATALOG[error_type].severity_range[1]
                )
                
                # Apply error impact
                kpi_vector_with_error, _ = self.injector.apply_errors_to_kpi_vector(kpi_vector, current_time=0.0)
                
                # Manually inject if above method didn't work (fallback)
                # This ensures we actually have error-modified data
                if np.allclose(kpi_vector, kpi_vector_with_error):
                    # Fallback: manually apply error using KPIImpactCalculator
                    kpi_dict = self._vector_to_kpi_dict(kpi_vector)
                    for cell_id in range(6):
                        for metric_name in kpi_dict[cell_id].keys():
                            original_val = kpi_dict[cell_id][metric_name]
                            modified_val = KPIImpactCalculator.apply_error_impact(
                                kpi_name=metric_name,
                                current_value=original_val,
                                error_type=error_type,
                                severity=severity
                            )
                            kpi_dict[cell_id][metric_name] = modified_val
                    kpi_vector_with_error = self._kpi_dict_to_vector(kpi_dict)
                
                # Create augmented sample
                augmented_sample = original_sample.copy()
                augmented_sample = self._update_sample_with_kpi_vector(
                    augmented_sample,
                    kpi_vector_with_error
                )
                
                # Add error metadata
                augmented_sample['_error_type'] = error_type.value
                augmented_sample['_error_severity'] = float(severity)
                
                augmented_data.append(augmented_sample)
                self.generated_samples += 1
                
                if (sample_num + 1) % max(1, errors_per_type // 5) == 0:
                    print(f"  Generated {sample_num + 1}/{errors_per_type} {error_type.value} samples")
        
        # Convert to DataFrame
        df_augmented = pd.DataFrame(augmented_data)
        print(f"\nFinal augmented dataset: {len(df_augmented)} samples")
        print(f"  - Original: {len(df_original)}")
        print(f"  - Error-augmented: {self.generated_samples}")
        
        # Save augmented dataset
        df_augmented.to_csv(output_data_path, index=False)
        print(f"\n✓ Augmented dataset saved to {output_data_path}")
        
        return str(output_data_path)
    
    def _extract_kpi_vector(self, sample: Dict) -> List[float]:
        """Extract 42-element KPI vector from a sample."""
        kpi_vector = []
        
        # Column mapping
        col_mapping = [
            ("Th_ENB", "throughput"),
            ("Delay_ENB", "delay"),
            ("Loss_ENB", "packet_loss"),
            ("UE_ENB", "ue_count"),
            ("RSRP_ENB", "rsrp"),
            ("SINR_ENB", "sinr"),
            ("Load_ENB", "cell_load")
        ]
        
        # For each cell (1-6) and each metric
        for cell_id in range(1, 7):
            for col_prefix, _ in col_mapping:
                col_name = f"{col_prefix}{cell_id}"
                value = sample.get(col_name, 0.0)
                kpi_vector.append(float(value))
        
        return kpi_vector
    
    def _vector_to_kpi_dict(self, kpi_vector: List[float]) -> Dict:
        """Convert flat vector to per-cell KPI dictionary."""
        kpi_dict = {}
        metrics = ["throughput", "delay", "packet_loss", "ue_count", "rsrp", "sinr", "cell_load"]
        
        for cell_id in range(6):
            start_idx = cell_id * 7
            kpi_dict[cell_id] = {}
            for metric_idx, metric_name in enumerate(metrics):
                kpi_dict[cell_id][metric_name] = kpi_vector[start_idx + metric_idx]
        
        return kpi_dict
    
    def _kpi_dict_to_vector(self, kpi_dict: Dict) -> List[float]:
        """Convert per-cell KPI dictionary back to flat vector."""
        vector = []
        metrics = ["throughput", "delay", "packet_loss", "ue_count", "rsrp", "sinr", "cell_load"]
        
        for cell_id in range(6):
            for metric in metrics:
                vector.append(kpi_dict[cell_id].get(metric, 0.0))
        
        return vector
    
    def _update_sample_with_kpi_vector(self, sample: Dict, kpi_vector: List[float]) -> Dict:
        """Update sample dictionary with new KPI values."""
        col_mapping = [
            ("Th_ENB", "throughput"),
            ("Delay_ENB", "delay"),
            ("Loss_ENB", "packet_loss"),
            ("UE_ENB", "ue_count"),
            ("RSRP_ENB", "rsrp"),
            ("SINR_ENB", "sinr"),
            ("Load_ENB", "cell_load")
        ]
        
        for cell_id in range(1, 7):
            for metric_idx, (col_prefix, _) in enumerate(col_mapping):
                col_name = f"{col_prefix}{cell_id}"
                vector_idx = (cell_id - 1) * 7 + metric_idx
                sample[col_name] = float(kpi_vector[vector_idx])
        
        return sample


def generate_error_aware_training_data(
    input_data_path: str,
    output_data_path: str = None,
    multiplier: float = 1.0
) -> str:
    """
    Convenience function to augment training data with errors.
    
    Usage:
        generate_error_aware_training_data(
            "data/training_dataset.csv",
            "data/training_dataset_with_errors.csv",
            multiplier=1.0  # Double the dataset size with error scenarios
        )
    """
    generator = ErrorDataGenerator()
    return generator.augment_training_data(input_data_path, output_data_path, multiplier)


if __name__ == "__main__":
    # Example usage
    project_root = Path(__file__).parent.parent
    training_data = project_root / "data" / "training_dataset.csv"
    
    if training_data.exists():
        generate_error_aware_training_data(
            str(training_data),
            str(training_data),  # Overwrite with augmented data
            multiplier=0.5  # Add 50% more samples
        )
    else:
        print(f"Training data not found at {training_data}")
