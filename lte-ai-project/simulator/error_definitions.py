"""
Error definitions and error types for the cellular network simulator.
Defines how each error type affects KPI metrics.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple
import numpy as np

class ErrorType(Enum):
    """Enumeration of all supported error types."""
    CONGESTION = "congestion"
    UNDERUTILIZATION = "underutilization"
    INTERFERENCE = "interference"
    EQUIPMENT_DEGRADATION = "equipment_degradation"
    JAMMING = "jamming"
    DDOS = "ddos"
    WEATHER = "weather"
    HANDOVER_FAILURE = "handover_failure"
    NONE = "none"


@dataclass
class ErrorDefinition:
    """Defines an error type and its impact on KPI metrics."""
    
    error_type: ErrorType
    description: str
    affected_metrics: list  # Which KPIs this error impacts
    severity_range: Tuple[float, float]  # (min, max) severity 0-1
    typical_duration: int  # Seconds
    
    def __post_init__(self):
        if not (0 <= self.severity_range[0] <= self.severity_range[1] <= 1):
            raise ValueError("Severity range must be between 0 and 1")


# Error Definitions Catalog
ERROR_CATALOG = {
    ErrorType.CONGESTION: ErrorDefinition(
        error_type=ErrorType.CONGESTION,
        description="Sudden spike in user equipment count or traffic",
        affected_metrics=["ue_count", "throughput", "delay", "packet_loss", "cell_load"],
        severity_range=(0.3, 1.0),
        typical_duration=30
    ),
    
    ErrorType.UNDERUTILIZATION: ErrorDefinition(
        error_type=ErrorType.UNDERUTILIZATION,
        description="Sudden drop in user equipment count",
        affected_metrics=["ue_count", "cell_load", "throughput"],
        severity_range=(0.2, 0.8),
        typical_duration=45
    ),
    
    ErrorType.INTERFERENCE: ErrorDefinition(
        error_type=ErrorType.INTERFERENCE,
        description="RF interference or signal degradation",
        affected_metrics=["sinr", "rsrp", "packet_loss", "throughput"],
        severity_range=(0.4, 1.0),
        typical_duration=60
    ),
    
    ErrorType.EQUIPMENT_DEGRADATION: ErrorDefinition(
        error_type=ErrorType.EQUIPMENT_DEGRADATION,
        description="Equipment malfunction (overheating, power supply degradation)",
        affected_metrics=["throughput", "delay", "packet_loss", "rsrp"],
        severity_range=(0.5, 1.0),
        typical_duration=120
    ),
    
    ErrorType.JAMMING: ErrorDefinition(
        error_type=ErrorType.JAMMING,
        description="Deliberate signal jamming attack",
        affected_metrics=["sinr", "packet_loss", "rsrp", "throughput", "delay"],
        severity_range=(0.6, 1.0),
        typical_duration=30
    ),
    
    ErrorType.DDOS: ErrorDefinition(
        error_type=ErrorType.DDOS,
        description="Distributed Denial of Service attack",
        affected_metrics=["packet_loss", "throughput", "delay", "cell_load"],
        severity_range=(0.7, 1.0),
        typical_duration=45
    ),
    
    ErrorType.WEATHER: ErrorDefinition(
        error_type=ErrorType.WEATHER,
        description="Adverse weather conditions (rain, snow, extreme temperature)",
        affected_metrics=["rsrp", "sinr", "throughput", "packet_loss"],
        severity_range=(0.2, 0.7),
        typical_duration=180  # Weather effects longer
    ),
    
    ErrorType.HANDOVER_FAILURE: ErrorDefinition(
        error_type=ErrorType.HANDOVER_FAILURE,
        description="Handover failures and cell reselection issues",
        affected_metrics=["handover_count", "packet_loss", "delay"],
        severity_range=(0.3, 0.9),
        typical_duration=60
    ),
}


class KPIImpactCalculator:
    """Calculates how an error affects KPI metrics."""
    
    @staticmethod
    def apply_error_impact(
        kpi_name: str,
        current_value: float,
        error_type: ErrorType,
        severity: float,
        baseline_value: float = None
    ) -> float:
        """
        Apply error impact to a KPI metric.
        
        Args:
            kpi_name: Name of the KPI (e.g., "throughput", "delay")
            current_value: Current KPI value
            error_type: Type of error being applied
            severity: Error severity (0-1)
            baseline_value: Baseline/normal value for the KPI (for normalized metrics)
        
        Returns:
            Modified KPI value
        """
        
        # Metrics that increase with errors (bad)
        increasing_metrics = ["delay", "packet_loss", "handover_count"]
        
        # Metrics that decrease with errors (bad)
        decreasing_metrics = ["throughput", "rsrp", "sinr", "cell_utilization"]
        
        # Metrics affected by population changes
        population_metrics = ["ue_count", "cell_load"]
        
        if error_type == ErrorType.CONGESTION:
            if kpi_name == "ue_count":
                return current_value * (1 + severity * 4)  # 4x multiplier at max severity
            elif kpi_name == "throughput":
                return current_value * (1 - severity * 0.6)
            elif kpi_name == "delay":
                return current_value * (1 + severity * 3)
            elif kpi_name == "packet_loss":
                return min(100, current_value + severity * 30)
            elif kpi_name == "cell_load":
                return min(1.0, current_value + severity * 0.7)
        
        elif error_type == ErrorType.UNDERUTILIZATION:
            if kpi_name == "ue_count":
                return max(0, current_value * (1 - severity * 0.8))
            elif kpi_name == "cell_load":
                return max(0, current_value * (1 - severity * 0.8))
        
        elif error_type == ErrorType.INTERFERENCE:
            if kpi_name == "sinr":
                return max(-20, current_value - severity * 20)
            elif kpi_name == "rsrp":
                return current_value - severity * 15
            elif kpi_name == "packet_loss":
                return min(100, current_value + severity * 25)
            elif kpi_name == "throughput":
                return current_value * (1 - severity * 0.5)
        
        elif error_type == ErrorType.EQUIPMENT_DEGRADATION:
            if kpi_name == "throughput":
                return current_value * (1 - severity * 0.7)
            elif kpi_name == "delay":
                return current_value * (1 + severity * 2)
            elif kpi_name == "packet_loss":
                return min(100, current_value + severity * 40)
            elif kpi_name == "rsrp":
                return current_value - severity * 10
        
        elif error_type == ErrorType.JAMMING:
            if kpi_name == "sinr":
                return max(-30, current_value - severity * 30)
            elif kpi_name == "packet_loss":
                return min(100, current_value + severity * 80)
            elif kpi_name == "rsrp":
                return current_value - severity * 20
            elif kpi_name == "throughput":
                return current_value * (1 - severity * 0.9)
            elif kpi_name == "delay":
                return current_value * (1 + severity * 5)
        
        elif error_type == ErrorType.DDOS:
            if kpi_name == "packet_loss":
                return min(100, current_value + severity * 90)
            elif kpi_name == "throughput":
                return current_value * (1 - severity * 0.95)
            elif kpi_name == "delay":
                return current_value * (1 + severity * 10)
            elif kpi_name == "cell_load":
                return min(1.0, current_value + severity * 0.9)
        
        elif error_type == ErrorType.WEATHER:
            if kpi_name == "rsrp":
                return current_value - severity * 10
            elif kpi_name == "sinr":
                return current_value - severity * 8
            elif kpi_name == "throughput":
                return current_value * (1 - severity * 0.3)
            elif kpi_name == "packet_loss":
                return min(100, current_value + severity * 15)
        
        elif error_type == ErrorType.HANDOVER_FAILURE:
            if kpi_name == "handover_count":
                return current_value + severity * 10
            elif kpi_name == "packet_loss":
                return min(100, current_value + severity * 20)
            elif kpi_name == "delay":
                return current_value * (1 + severity * 1.5)
        
        # Default: no change if no matching rule
        return current_value
    
    @staticmethod
    def get_affected_metrics(error_type: ErrorType) -> list:
        """Get list of metrics affected by this error type."""
        if error_type in ERROR_CATALOG:
            return ERROR_CATALOG[error_type].affected_metrics
        return []
    
    @staticmethod
    def get_error_description(error_type: ErrorType) -> str:
        """Get description of error type."""
        if error_type in ERROR_CATALOG:
            return ERROR_CATALOG[error_type].description
        return "Unknown error type"


def validate_error_type(error_type_str: str) -> bool:
    """Validate if a string is a valid error type."""
    try:
        ErrorType(error_type_str.lower())
        return True
    except ValueError:
        return False


def get_all_error_types() -> list:
    """Get list of all supported error types."""
    return [e.value for e in ErrorType if e != ErrorType.NONE]
