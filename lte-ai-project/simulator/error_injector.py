"""
Error Injector Module

Handles injecting errors into the simulator and tracking error events.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, List
import json
from simulator.error_definitions import ErrorType, KPIImpactCalculator, ERROR_CATALOG


@dataclass
class ErrorEvent:
    """Represents an active error event in the network."""
    
    error_type: ErrorType
    cell_id: int
    severity: float  # 0-1
    start_time: float  # Simulation time
    duration: float  # Seconds
    end_time: Optional[float] = None
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.end_time is None:
            self.end_time = self.start_time + self.duration
    
    def is_active(self, current_time: float) -> bool:
        """Check if error is still active at given time."""
        return self.start_time <= current_time < self.end_time
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type.value,
            "cell_id": self.cell_id,
            "severity": self.severity,
            "start_time": self.start_time,
            "duration": self.duration,
            "end_time": self.end_time,
            "is_active": self.is_active(self.start_time + self.duration / 2),
            "created_at": self.created_at
        }


class ErrorInjector:
    """
    Manages error injection into the network simulator.
    
    Allows injecting various error types, tracking active errors,
    and applying their effects to KPI metrics.
    """
    
    def __init__(self):
        """Initialize the error injector."""
        self.active_errors: List[ErrorEvent] = []
        self.error_history: List[ErrorEvent] = []
        self.error_impact_log: List[Dict] = []
    
    def inject_error(
        self,
        error_type: str,
        cell_id: int,
        severity: float,
        start_time: float,
        duration: float = None
    ) -> Optional[ErrorEvent]:
        """
        Inject an error into the network.
        
        Args:
            error_type: Type of error (from ErrorType enum)
            cell_id: Target cell ID (0-5)
            severity: Severity level (0-1)
            start_time: Simulation time when error starts
            duration: How long the error lasts (if None, uses default)
        
        Returns:
            ErrorEvent object if successful, None otherwise
        """
        try:
            # Validate error type
            err_type = ErrorType(error_type.lower())
        except ValueError:
            print(f"ERROR: Invalid error type '{error_type}'")
            return None
        
        # Validate cell ID
        if not (0 <= cell_id < 6):
            print(f"ERROR: Invalid cell ID {cell_id}. Must be 0-5")
            return None
        
        # Validate severity
        if not (0 <= severity <= 1):
            print(f"ERROR: Severity must be between 0 and 1, got {severity}")
            return None
        
        # Get duration from catalog if not provided
        if duration is None:
            if err_type in ERROR_CATALOG:
                duration = ERROR_CATALOG[err_type].typical_duration
            else:
                duration = 30
        
        # Create error event
        error_event = ErrorEvent(
            error_type=err_type,
            cell_id=cell_id,
            severity=severity,
            start_time=start_time,
            duration=duration
        )
        
        self.active_errors.append(error_event)
        self.error_history.append(error_event)
        
        print(f"[ErrorInjector] Injected {error_type} on cell {cell_id} "
              f"(severity={severity:.2f}, duration={duration}s)")
        
        return error_event
    
    def get_active_errors(self, current_time: float) -> List[ErrorEvent]:
        """Get list of currently active errors."""
        return [e for e in self.active_errors if e.is_active(current_time)]
    
    def update_active_errors(self, current_time: float):
        """Remove expired errors from active list."""
        self.active_errors = [e for e in self.active_errors 
                            if e.is_active(current_time)]
    
    def apply_error_effects(
        self,
        kpi_values: Dict[str, float],
        cell_id: int,
        current_time: float
    ) -> Dict[str, float]:
        """
        Apply effects of active errors to KPI values.
        
        Args:
            kpi_values: Dictionary of current KPI values
            cell_id: Target cell
            current_time: Current simulation time
        
        Returns:
            Modified KPI values
        """
        affected_errors = [e for e in self.active_errors 
                          if e.cell_id == cell_id and e.is_active(current_time)]
        
        if not affected_errors:
            return kpi_values
        
        modified_kpis = kpi_values.copy()
        
        # Apply effects from each active error
        for error in affected_errors:
            for kpi_name, kpi_value in modified_kpis.items():
                new_value = KPIImpactCalculator.apply_error_impact(
                    kpi_name=kpi_name,
                    current_value=kpi_value,
                    error_type=error.error_type,
                    severity=error.severity,
                    baseline_value=kpi_values.get(kpi_name)
                )
                
                modified_kpis[kpi_name] = new_value
                
                # Log impact
                self.error_impact_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "simulation_time": current_time,
                    "cell_id": cell_id,
                    "error_type": error.error_type.value,
                    "kpi_name": kpi_name,
                    "original_value": kpi_value,
                    "modified_value": new_value,
                    "severity": error.severity
                })
        
        return modified_kpis
    
    def get_status(self, current_time: float = None) -> dict:
        """Get current error injector status."""
        if current_time is None:
            current_time = 0
        
        active = self.get_active_errors(current_time)
        
        return {
            "total_errors_injected": len(self.error_history),
            "active_errors": len(active),
            "active_error_details": [e.to_dict() for e in active],
            "impact_log_entries": len(self.error_impact_log)
        }
    
    def clear_history(self):
        """Clear error history (keep for analysis)."""
        print("[ErrorInjector] Clearing error history")
        self.active_errors.clear()
        self.error_history.clear()
        self.error_impact_log.clear()
    
    def export_impact_log(self, filepath: str):
        """Export error impact log to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.error_impact_log, f, indent=2)
        print(f"[ErrorInjector] Impact log exported to {filepath}")


# Singleton instance
_injector_instance = None


def get_error_injector() -> ErrorInjector:
    """Get the global error injector instance."""
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = ErrorInjector()
    return _injector_instance


def init_error_injector() -> ErrorInjector:
    """Initialize the error injector."""
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = ErrorInjector()
    return _injector_instance
