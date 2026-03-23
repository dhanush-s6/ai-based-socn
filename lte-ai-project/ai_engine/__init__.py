"""
AI Engine Package

Contains:
- hybrid_predictor.py: Anomaly detection + trend prediction model
- model_updater.py: Continuous model retraining system
"""

from .hybrid_predictor import HybridPredictor
from .model_updater import ModelUpdater, get_model_updater, init_model_updater

__all__ = [
    "HybridPredictor",
    "ModelUpdater",
    "get_model_updater",
    "init_model_updater"
]
