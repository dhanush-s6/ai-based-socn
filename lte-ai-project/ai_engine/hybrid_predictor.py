import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, List, Dict, Any
from sklearn.ensemble import IsolationForest, GradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import StandardScaler
import joblib
from ai_engine.neighbor_manager import NeighborManager
from ai_engine.smart_labeler import SmartLabeler

class HybridPredictor:
    """
    Hybrid AI model combining anomaly detection and trend prediction.
    
    - Anomaly Detection: Uses Isolation Forest to detect abnormal KPI patterns
    - Trend Prediction: Uses Gradient Boosting to predict future failures
    """
    
    def __init__(self, config_path: str = None):
        """Initialize the hybrid predictor."""
        self.config = config_path
        self.anomaly_detector = None
        self.trend_predictor = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = self._get_feature_names()
        self.model_version = "1.0"
        self.neighbor_manager = NeighborManager()
        self.smart_labeler = SmartLabeler()
    
    def _get_feature_names(self) -> List[str]:
        """Get KPI feature names for a single tower."""
        return [
            "throughput", "delay", "packet_loss", "ue_count",
            "rsrp", "sinr", "cell_load"
        ]
    
    def train(self, training_data_path: str, test_size: float = 0.2):
        """
        Train both anomaly detection and trend prediction models.
        
        Args:
            training_data_path: Path to training CSV file
            test_size: Proportion of data for testing
        """
        print(f"Loading training data from {training_data_path}...")
        df = pd.read_csv(training_data_path)
        
        # Extract base features (42), then augment with neighbor context for learning load balancing.
        X_base = self._extract_features(df)
        X = self._augment_for_model(X_base)
        
        if X.shape[0] == 0:
            raise ValueError("No valid training data found")
        
        print(f"Training data shape: {X.shape}")
        
        # Normalize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train anomaly detector (Isolation Forest)
        print("Training anomaly detector...")
        self.anomaly_detector = IsolationForest(
            contamination=0.1,
            n_estimators=100,
            random_state=42
        )
        self.anomaly_detector.fit(X_scaled)
        
        # Generate smart SON labels (0..3) that encode balancing behavior.
        y = self._generate_smart_labels(df)
        
        # Check if we have enough class diversity for training the classifier
        unique_classes = np.unique(y)
        print(f"Label distribution: {np.bincount(y)}")
        
        # Train trend predictor (Gradient Boosting)
        print("Training trend predictor...")
        
        if len(unique_classes) < 2:
            print(f"⚠ Warning: Only {len(unique_classes)} class(es) in labels. Using dummy predictor.")
            # Create dummy predictor that always returns the majority class
            self.trend_predictor = DummyClassifier(strategy='most_frequent', random_state=42)
            self.trend_predictor.fit(X_scaled, y)
        else:
            self.trend_predictor = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
            self.trend_predictor.fit(X_scaled, y)
        
        self.is_trained = True
        print("✓ Hybrid model training completed")
    
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extract feature matrix from CSV data."""
        features_list = []
        
        # Map NS3 column names to our features
        column_mapping = {
            "Th_ENB": "throughput",
            "Delay_ENB": "delay", 
            "Loss_ENB": "packet_loss",
            "UE_ENB": "ue_count",
            "RSRP_ENB": "rsrp",
            "SINR_ENB": "sinr",
            "Load_ENB": "cell_load"
        }
        
        # For each enb (1-6), collect metrics in order
        for enb_id in range(1, 7):
            for ns3_col, feature_name in column_mapping.items():
                col_name = f"{ns3_col}{enb_id}"
                if col_name in df.columns:
                    features_list.append(col_name)
        
        if not features_list:
            print(f"Warning: Could not find expected feature columns.")
            print(f"Available columns: {df.columns.tolist()}")
            return np.array([])
        
        return df[features_list].fillna(0).values
    
    def _generate_trend_labels(self, df: pd.DataFrame) -> np.ndarray:
        """
        Generate binary labels for trend prediction.
        1 = Bad trend (approaching failure), 0 = Normal trend
        """
        labels = []
        delay_cols = [col for col in df.columns if 'delay' in col.lower()]
        loss_cols = [col for col in df.columns if 'loss' in col.lower()]
        load_cols = [col for col in df.columns if 'load' in col.lower()]
        sinr_cols = [col for col in df.columns if 'sinr' in col.lower()]
        
        for idx, row in df.iterrows():
            # Mark as bad if any of these conditions:
            # - Average delay > 50ms (elevated)
            # - Average loss > 0.01 (elevated)
            # - Average load > 0.85 (congested)
            # - Average SINR < 5dB (poor signal)
            
            avg_delay = row[delay_cols].mean() if delay_cols else 0
            avg_loss = row[loss_cols].mean() if loss_cols else 0
            avg_load = row[load_cols].mean() if load_cols else 0
            avg_sinr = row[sinr_cols].mean() if sinr_cols else 20
            
            is_bad = (avg_delay > 50 or avg_loss > 0.01 or 
                     avg_load > 0.85 or avg_sinr < 5)
            
            label = 1 if is_bad else 0
            labels.append(label)
        
        return np.array(labels)

    def _generate_smart_labels(self, df: pd.DataFrame) -> np.ndarray:
        """Generate multiclass SON labels with fallback to binary trend labels."""
        try:
            labels = self.smart_labeler.generate_labels(df)
            if labels is not None and len(labels) == len(df):
                unique = np.unique(labels)
                if len(unique) >= 2:
                    return labels.astype(int)
        except Exception as e:
            print(f"Warning: Smart label generation failed ({e}), using fallback labels")

        return self._generate_trend_labels(df).astype(int)

    def _augment_for_model(self, X_base: np.ndarray) -> np.ndarray:
        """Augment base 42 features with neighbor-aware features for model training/inference."""
        if X_base.size == 0:
            return X_base
        try:
            return self.neighbor_manager.augment_features(X_base)
        except Exception as e:
            print(f"Warning: Neighbor augmentation failed ({e}), using base features")
            return X_base

    def _prepare_runtime_features(self, kpi_state: List[float]) -> np.ndarray:
        """Prepare runtime feature vector matching model's trained feature dimensionality."""
        base = np.array(kpi_state, dtype=float).reshape(1, -1)
        expected = self._expected_model_feature_count()

        if expected == base.shape[1]:
            return base

        # Try neighbor-augmented representation when model expects more than 42 features.
        if expected > base.shape[1]:
            augmented = self._augment_for_model(base)
            if augmented.shape[1] == expected:
                return augmented
            if augmented.shape[1] > expected:
                return augmented[:, :expected]

            # Pad as conservative fallback if model expects slightly larger vectors.
            padded = np.pad(augmented, ((0, 0), (0, expected - augmented.shape[1])), constant_values=0.0)
            return padded

        # Model expects fewer features than runtime vector.
        return base[:, :expected]

    def _expected_model_feature_count(self) -> int:
        """Infer feature count expected by loaded model artifacts."""
        if hasattr(self.scaler, "n_features_in_"):
            return int(self.scaler.n_features_in_)
        if self.anomaly_detector is not None and hasattr(self.anomaly_detector, "n_features_in_"):
            return int(self.anomaly_detector.n_features_in_)
        return len(self.feature_names) * 6
    
    def predict(self, kpi_state: List[float]) -> Dict[str, Any]:
        """
        Make predictions on current network state.
        
        Args:
            kpi_state: List of 42 KPI values (7 features × 6 towers)
        
        Returns:
            Dictionary with anomaly scores, risk probabilities, and recommended action
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        # Reshape base input and prepare model features based on trained dimensionality.
        X_base = np.array(kpi_state).reshape(1, -1)
        X = self._prepare_runtime_features(kpi_state)
        
        # Validate feature count
        # Model expects 42 features (7 features × 6 towers)
        # Format: [Th1, Delay1, Loss1, UE1, RSRP1, SINR1, Load1, 
        #          Th2, Delay2, Loss2, UE2, RSRP2, SINR2, Load2, ... Th6...Load6]
        expected_features = len(self.feature_names) * 6  # Base input should be 42
        
        if X_base.shape[1] != expected_features:
            raise ValueError(f"Expected {expected_features} features, got {X_base.shape[1]}. KPI data from simulator does not match model expectations.")
        
        # Normalize
        try:
            X_scaled = self.scaler.transform(X)
        except:
            X_scaled = X
        
        # Get overall anomaly score on full data
        overall_anomaly_score = abs(self.anomaly_detector.score_samples(X_scaled)[0])
        
        # Get failure probability with safe access to prevent index errors
        try:
            model_hint_action = int(self.trend_predictor.predict(X_scaled)[0]) if self.trend_predictor is not None else 0
            if hasattr(self.trend_predictor, 'predict_proba'):
                proba = self.trend_predictor.predict_proba(X_scaled)[0]
                if len(proba) >= 4:
                    # Multiclass (0..3): combine risk-oriented classes into failure probability.
                    overall_failure_prob = float(min(1.0, proba[3] + 0.6 * proba[1] + 0.4 * proba[2]))
                elif len(proba) > 1:
                    overall_failure_prob = float(proba[1])
                else:
                    overall_failure_prob = float(proba[0])
            else:
                overall_failure_prob = float(model_hint_action)
        except IndexError as e:
            print(f"Warning: Error accessing prediction probability: {e}. Using default 0.0")
            overall_failure_prob = 0.0
            model_hint_action = 0
        
        # Get predictions
        predictions = {
            "timestamp": self._get_timestamp(),
            "overall_anomaly_score": float(overall_anomaly_score),
            "overall_failure_probability": float(overall_failure_prob),
            "cells": []
        }

        # Parse all cells once for neighbor-aware policy checks
        cell_metrics_map = self._parse_cell_metrics(kpi_state)
        lb_recommendations = self.neighbor_manager.recommend_load_rebalancing(cell_metrics_map)
        lb_scores = self.neighbor_manager.load_balance_score(cell_metrics_map)
        
        # Parse per-cell predictions (estimate based on cell KPIs)
        for cell_id in range(6):
            # Extract this cell's features
            start_idx = cell_id * len(self.feature_names)
            end_idx = start_idx + len(self.feature_names)
            cell_kpis = kpi_state[start_idx:end_idx]
            
            # Simple heuristic: if cell is worse than average, increase anomaly score
            # Extract corresponding scaled features for context
            cell_features_scaled = X_scaled[0, start_idx:end_idx]
            
            # Estimate per-cell anomaly based on deviation from normal
            # Use the mean absolute deviation as proxy for anomaly in this cell
            cell_deviation = np.abs(cell_features_scaled).mean()
            
            # Determine action based on overall scores and cell deviation
            cell_anomaly = overall_anomaly_score * (1.0 + cell_deviation)
            cell_failure_prob = overall_failure_prob + (0.1 * cell_deviation)
            action = self._decide_action(cell_anomaly, cell_failure_prob, model_hint_action=model_hint_action)

            # Apply explicit load balancing policy (cross-cell aware)
            cell_id_1 = cell_id + 1
            lb_reco = lb_recommendations.get(cell_id_1, "BALANCE")
            action, lb_meta = self._apply_load_balance_policy(
                action=action,
                cell_id=cell_id_1,
                recommendation=lb_reco,
                cell_metrics=cell_metrics_map.get(cell_id_1, {}),
                all_cell_metrics=cell_metrics_map,
            )

            # Apply neighbor-aware safety policy before returning action
            action = self._apply_neighbor_safety_policy(
                action=action,
                cell_id=cell_id_1,
                cell_metrics=cell_metrics_map.get(cell_id_1, {}),
                all_cell_metrics=cell_metrics_map,
                anomaly_score=float(cell_anomaly),
                failure_prob=float(min(1.0, cell_failure_prob)),
            )
            
            predictions["cells"].append({
                "cell_id": cell_id,
                "anomaly_score": float(cell_anomaly),
                "failure_probability": float(min(1.0, cell_failure_prob)),
                "action": action,
                "model_hint_action": int(model_hint_action),
                "load_balance_recommendation": lb_reco,
                "load_balance_score": float(lb_scores.get(cell_id_1, 0.5)),
                "load_imbalance": float(lb_meta.get("load_imbalance", 0.0)),
                "handover_target": lb_meta.get("handover_target"),
                "kpis": dict(zip(self.feature_names, cell_kpis))
            })
        
        return predictions

    def _parse_cell_metrics(self, kpi_state: List[float]) -> Dict[int, Dict[str, float]]:
        """Convert flat 42-feature vector into per-cell KPI dictionary (1-indexed)."""
        cells = {}
        metrics_per_cell = len(self.feature_names)
        for cell_id in range(1, 7):
            start_idx = (cell_id - 1) * metrics_per_cell
            values = kpi_state[start_idx:start_idx + metrics_per_cell]
            if len(values) < metrics_per_cell:
                values = values + [0.0] * (metrics_per_cell - len(values))

            cells[cell_id] = {
                "throughput": float(values[0]),
                "delay": float(values[1]),
                "packet_loss": float(values[2]),
                "ue_count": float(values[3]),
                "rsrp": float(values[4]),
                "sinr": float(values[5]),
                "cell_load": float(values[6]),
            }
        return cells

    def _apply_neighbor_safety_policy(
        self,
        action: int,
        cell_id: int,
        cell_metrics: Dict[str, float],
        all_cell_metrics: Dict[int, Dict[str, float]],
        anomaly_score: float,
        failure_prob: float,
    ) -> int:
        """Guardrails to prevent invalid handovers and improve action realism."""
        if not cell_metrics:
            return action

        delay = cell_metrics.get("delay", 0.0)
        loss = cell_metrics.get("packet_loss", 0.0)
        sinr = cell_metrics.get("sinr", 0.0)
        load = cell_metrics.get("cell_load", 0.0)

        neighbor_features = self.neighbor_manager._calculate_neighbor_features(cell_id, all_cell_metrics)
        avg_neighbor_load = float(neighbor_features[0]) if neighbor_features else 1.0
        min_neighbor_delay = float(neighbor_features[1]) if neighbor_features else 999.0
        max_neighbor_sinr = float(neighbor_features[2]) if neighbor_features else -150.0

        # Handover is allowed only under persistent severe degradation AND a viable neighbor exists.
        if action == 3:
            severe_local = (failure_prob > 0.97) or (load > 0.92 and (delay > 120 or sinr < 2.5 or loss > 8.0))
            viable_neighbor = (avg_neighbor_load < 0.85) and (max_neighbor_sinr > sinr) and (min_neighbor_delay < delay)
            if not (severe_local and viable_neighbor):
                # Fall back to less disruptive control action first.
                if sinr < 5.0 or anomaly_score > 1.4:
                    return 1
                if load > 0.85 or delay > 80.0:
                    return 2
                return 0

        # Avoid power down under clearly bad RF conditions.
        if action == 2 and (sinr < 4.0 or delay > 100.0):
            return 1

        return action
    
    def _decide_action(self, anomaly_score: float, failure_prob: float, model_hint_action: int = 0) -> int:
        """
        Decide action based on anomaly and failure probability scores.
        
        Actions:
            0 = Balance (normal operation)
            1 = Increase Power + Load Balancing
            2 = Reduce Power + Carrier Aggregation
            3 = Initiate Handover
        """
        # More conservative thresholds to reduce false positives
        anomaly_threshold = 1.5      # Only trigger for significant anomalies
        failure_threshold = 0.85     # Only severe failures trigger immediate action
        power_up_threshold = 1.2     # Power up for moderate issues
        power_down_threshold = 0.9   # Power down for mild issues
        
        # Learned hint from trend model (especially useful with smart multiclass labels).
        if model_hint_action in (1, 2, 3) and failure_prob > 0.55:
            return model_hint_action

        # Handover is only for extreme conditions
        if failure_prob > 0.95:
            return 3  # Extreme: Initiate handover
        
        # Check anomaly scores for other actions
        if anomaly_score > anomaly_threshold or failure_prob > failure_threshold:
            if anomaly_score > 1.5:
                return 1  # Anomaly detected: Increase power
            elif anomaly_score > power_down_threshold:
                return 2  # Preventive: Reduce power
        
        return 0  # Normal operation

    def _apply_load_balance_policy(
        self,
        action: int,
        cell_id: int,
        recommendation: str,
        cell_metrics: Dict[str, float],
        all_cell_metrics: Dict[int, Dict[str, float]],
    ) -> Tuple[int, Dict[str, Any]]:
        """Enforce explicit balancing behavior using neighbor-aware recommendations."""
        meta: Dict[str, Any] = {"handover_target": None, "load_imbalance": 0.0}
        if not cell_metrics:
            return action, meta

        current_load = float(cell_metrics.get("cell_load", 0.0))
        neighbor_features = self.neighbor_manager._calculate_neighbor_features(cell_id, all_cell_metrics)
        avg_neighbor_load = float(neighbor_features[0]) if neighbor_features else current_load
        meta["load_imbalance"] = float(current_load - avg_neighbor_load)

        # If recommended to handover due to overload and a target exists, prioritize handover.
        if recommendation.startswith("HANDOVER_TO_"):
            try:
                target = int(recommendation.split("_")[-1])
                target_metrics = all_cell_metrics.get(target, {})
                target_load = float(target_metrics.get("cell_load", 1.0))
                if current_load > 0.80 and target_load < 0.72 and cell_metrics.get("ue_count", 0) > 0:
                    meta["handover_target"] = target
                    return 3, meta
            except Exception:
                pass

        # Underutilized cells should not aggressively handover out.
        if recommendation == "ACCEPT_HANDOVER" and current_load < 0.35 and action == 3:
            return 0, meta

        # If imbalance is high and this cell is overloaded, avoid passive actions.
        if meta["load_imbalance"] > 0.18 and current_load > 0.82 and action in (0, 2):
            targets = self.neighbor_manager.find_best_handover_targets(cell_id, all_cell_metrics)
            if targets:
                meta["handover_target"] = int(targets[0][0])
                return 3, meta

        return action, meta
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def save(self, model_path: str):
        """Save the trained model."""
        if not self.is_trained:
            raise RuntimeError("Cannot save untrained model")
        
        model_dict = {
            "anomaly_detector": self.anomaly_detector,
            "trend_predictor": self.trend_predictor,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "model_version": self.model_version
        }
        
        joblib.dump(model_dict, model_path)
        print(f"✓ Model saved to {model_path}")
    
    def load(self, model_path: str):
        """Load a previously trained model."""
        model_dict = joblib.load(model_path)
        self.anomaly_detector = model_dict["anomaly_detector"]
        self.trend_predictor = model_dict["trend_predictor"]
        self.scaler = model_dict["scaler"]
        self.feature_names = model_dict["feature_names"]
        self.model_version = model_dict.get("model_version", "1.0")
        self.is_trained = True
        print(f"✓ Model loaded from {model_path}")


if __name__ == "__main__":
    # Example usage
    predictor = HybridPredictor()
    
    # Check if training data exists
    training_data_path = "training_dataset.csv"
    if Path(training_data_path).exists():
        print(f"Training model on {training_data_path}...")
        predictor.train(training_data_path)
        predictor.save("models/network_ai_hybrid.pkl")
    else:
        print(f"Training data not found at {training_data_path}")
