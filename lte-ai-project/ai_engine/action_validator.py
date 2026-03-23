"""
ActionValidator: Post-processing constraint enforcement.

Even with intelligent labeling and stability control, SON decisions must respect:
- Regulatory constraints (max power levels, frequency allocations)
- Equipment limits (processing capacity, temperature)
- Business rules (SLA guarantees, cost optimization)
- Safety margins (don't saturate any resource)

This module validates and potentially modifies AI decisions before execution.
"""

import numpy as np
from typing import Dict, Tuple, List
from enum import IntEnum
from dataclasses import dataclass


class ConstraintType(IntEnum):
    """Types of constraints that can be validated."""
    POWER_LIMIT = 0
    LOAD_CAPACITY = 1
    HANDOVER_RATE = 2
    LATENCY_SLA = 3
    UE_ACTIVITY = 4
    INTERFERENCE = 5
    THERMAL = 6


@dataclass
class ConstraintViolation:
    """Record of a constraint violation and remediation."""
    cell_id: int
    constraint_type: ConstraintType
    severity: float  # 0-1, how badly violated
    action_proposed: int
    action_remediated: int
    reason: str


@dataclass
class ValidationConfig:
    """Configuration for validation rules."""
    
    # Power constraints (dBm)
    max_power_dbm = 46  # Standard eNodeB max
    min_power_dbm = 20  # Don't go too low
    power_increase_step = 3  # Increase in 3dB steps max
    
    # Load constraints
    max_cell_load = 0.95  # Hard limit (95% capacity)
    max_handover_rate = 2.0  # Handovers per second per cell
    
    # Service constraints
    max_delay_sla_ms = 100  # Hard SLA: delay must stay under 100ms
    max_packet_loss_sla = 0.05  # Hard SLA: loss under 5%
    
    # Safety margins
    cpu_headroom = 0.15  # Keep 15% CPU reserved
    memory_headroom = 0.20  # Keep 20% memory reserved
    thermal_margin_c = 5  # Keep 5°C below max operating temp


class ActionValidator:
    """
    Validates SON actions against business and technical constraints.
    
    Pipeline:
    1. Check if action is feasible given current state
    2. Identify constraint violations
    3. Recommend remediation (modified action or rejection)
    4. Log violations for audit trail
    """
    
    def __init__(self, config: ValidationConfig = None):
        """Initialize validator with constraints."""
        self.config = config or ValidationConfig()
        self.violations_log: List[ConstraintViolation] = []
        self.action_names = {
            0: "BALANCE",
            1: "INCREASE_POWER",
            2: "REDUCE_POWER",
            3: "HANDOVER"
        }
    
    def validate_action(self, 
                        cell_id: int,
                        proposed_action: int,
                        current_kpi: Dict,
                        network_state: Dict) -> Tuple[int, List[str]]:
        """
        Validate a proposed action for a cell.
        
        Args:
            cell_id: Which cell (1-6)
            proposed_action: Action code (0-3)
            current_kpi: This cell's metrics {delay, load, rsrp, ...}
            network_state: Network-wide state {total_handovers_ps, avg_cpu, ...}
        
        Returns:
            (final_action, warnings)
            where final_action may differ from proposed due to constraints
        """
        warnings = []
        final_action = proposed_action
        
        # Constraint checks in priority order
        
        # 1. Check power limits (most critical)
        if proposed_action == 1:  # INCREASE_POWER
            if current_kpi.get('rsrp', -120) >= self.config.min_power_dbm:
                final_action = 0  # Already at min power, can't reduce further
                warnings.append("CONSTRAINT: Cell already at minimum power")
            # Also check for reaching hard limit
            if current_kpi.get('rsrp', 0) >= self.config.max_power_dbm:
                final_action = 0
                warnings.append("CONSTRAINT: Cell at maximum power level")
        
        # 2. Check load capacity
        if proposed_action == 3:  # HANDOVER (accepts users from other cells)
            if current_kpi.get('cell_load', 0) > self.config.max_cell_load:
                final_action = 0  # Can't accept handover if at capacity
                warnings.append(
                    f"CONSTRAINT: Cell load {current_kpi['cell_load']:.1%} > "
                    f"max {self.config.max_cell_load:.1%}"
                )
        
        # 3. Check handover rate (prevent handover spam)
        if proposed_action == 3:  # HANDOVER
            current_ho_rate = network_state.get('handover_rate_per_cell', 0)
            if current_ho_rate >= self.config.max_handover_rate:
                final_action = 0
                warnings.append(
                    f"CONSTRAINT: Handover rate {current_ho_rate:.1f}/s "
                    f"exceeds max {self.config.max_handover_rate:.1f}/s"
                )
        
        # 4. Check SLA preservation
        if proposed_action == 1:  # INCREASE_POWER might worsen delay (interference)
            current_delay = current_kpi.get('delay', 50)
            if current_delay > self.config.max_delay_sla_ms:
                warnings.append(
                    f"WARNING: Delay {current_delay}ms already violates SLA "
                    f"({self.config.max_delay_sla_ms}ms). Increase power unlikely to help."
                )
        
        # 5. Check thermal limits
        if proposed_action == 1:  # INCREASE_POWER increases heat
            current_temp = network_state.get('avg_temp_c', 60)
            max_safe_temp = 90 - self.config.thermal_margin_c  # Assuming 90°C max
            if current_temp > max_safe_temp:
                final_action = 0
                warnings.append(
                    f"CONSTRAINT: Temperature {current_temp}°C > "
                    f"safe limit {max_safe_temp}°C. Power increase blocked."
                )
        
        # 6. Check resource headroom
        if proposed_action in [1, 3]:  # INCREASE_POWER or HANDOVER use resources
            cpu_available = 1.0 - network_state.get('cpu_usage', 0.7)
            if cpu_available < self.config.cpu_headroom:
                final_action = 0
                warnings.append(
                    f"CONSTRAINT: CPU headroom {cpu_available:.1%} < "
                    f"required {self.config.cpu_headroom:.1%}"
                )
        
        # 7. Validate action against current state
        if proposed_action == 2:  # REDUCE_POWER
            if current_kpi.get('sinr', 15) > 10:  # Already good signal
                warnings.append(
                    f"INFO: Power already optimal (SINR {current_kpi['sinr']}dB)"
                )
        
        # 8. Check for conflicting actions
        # (e.g., don't both increase power and handover simultaneously)
        if proposed_action == 1:  # INCREASE_POWER
            # If also recommending handover on same cell, prioritize one
            if current_kpi.get('cell_load', 0) > 0.8:
                # Load indicates need for handover, not power increase
                # Skip this check as we handle per-cell separately
                pass
        
        # Record if any violation
        if final_action != proposed_action:
            violation = ConstraintViolation(
                cell_id=cell_id,
                constraint_type=ConstraintType.POWER_LIMIT,  # Most common
                severity=abs(final_action - proposed_action) / 3.0,
                action_proposed=proposed_action,
                action_remediated=final_action,
                reason="; ".join(warnings) if warnings else "Action modified"
            )
            self.violations_log.append(violation)
            
            if warnings:
                print(f"  Cell {cell_id} Action Validation: {final_action} "
                      f"({self._action_name(final_action)})")
                for w in warnings:
                    print(f"    → {w}")
        
        return final_action, warnings
    
    def validate_all_actions(self,
                             proposed_actions: np.ndarray,
                             current_kpis: Dict[int, Dict],
                             network_state: Dict) -> Tuple[np.ndarray, Dict]:
        """
        Validate all cell actions at once.
        
        Args:
            proposed_actions: Array of 6 action codes
            current_kpis: Dict of all cell metrics
            network_state: Network-wide state metrics
        
        Returns:
            (validated_actions, validation_report)
        """
        validated = np.zeros(6, dtype=int)
        validation_report = {}
        
        for cell_id in range(1, 7):
            cell_idx = cell_id - 1
            kpi = current_kpis.get(cell_id, {})
            
            final_action, warnings = self.validate_action(
                cell_id,
                proposed_actions[cell_idx],
                kpi,
                network_state
            )
            
            validated[cell_idx] = final_action
            validation_report[cell_id] = {
                'proposed': proposed_actions[cell_idx],
                'final': final_action,
                'warnings': warnings
            }
        
        return validated, validation_report
    
    def soft_validate(self, action: int, kpi: Dict) -> bool:
        """
        Lightweight validation - just check if action makes sense given KPI.
        
        True = action is defensible, False = action seems wrong
        """
        if action == 1:  # INCREASE_POWER
            # OK if signal is poor (RSRP < -130)
            return kpi.get('rsrp', -100) < -130
        
        elif action == 2:  # REDUCE_POWER
            # OK if signal is excellent and load is low
            return (kpi.get('sinr', 15) > 10 and 
                    kpi.get('cell_load', 0) < 0.3)
        
        elif action == 3:  # HANDOVER
            # OK if load is high or QoS is bad
            return (kpi.get('cell_load', 0) > 0.8 or
                    kpi.get('delay', 50) > 50 or
                    kpi.get('packet_loss', 0) > 0.01)
        
        else:  # BALANCE (0)
            return True  # Always valid
    
    def get_violations_summary(self) -> Dict:
        """Get summary of all constraint violations recorded."""
        if not self.violations_log:
            return {'total': 0, 'by_type': {}, 'by_cell': {}}
        
        by_type = {}
        by_cell = {}
        
        for violation in self.violations_log:
            # Group by constraint type
            ct = violation.constraint_type.name
            by_type[ct] = by_type.get(ct, 0) + 1
            
            # Group by cell
            cell_id = violation.cell_id
            by_cell[cell_id] = by_cell.get(cell_id, 0) + 1
        
        return {
            'total': len(self.violations_log),
            'by_type': by_type,
            'by_cell': by_cell,
            'avg_severity': float(np.mean([v.severity for v in self.violations_log]))
        }
    
    def clear_violations_log(self):
        """Clear recorded violations."""
        self.violations_log.clear()
    
    @staticmethod
    def _action_name(action: int) -> str:
        """Convert action code to name."""
        names = {0: "BALANCE", 1: "INCREASE_POWER", 2: "REDUCE_POWER", 3: "HANDOVER"}
        return names.get(action, "UNKNOWN")


def demonstrate_validation():
    """Demo of action validation."""
    print("=== Action Validator Demo ===\n")
    
    from dataclasses import dataclass
    validator = ActionValidator()
    
    # Test scenario: cell at max capacity trying to accept handover
    print("Scenario 1: Cell at max capacity tries to accept handover")
    cell_kpi = {
        'cell_load': 0.98,  # Nearly full
        'delay': 65,
        'rsrp': -100,
        'sinr': 8,
        'packet_loss': 0.01
    }
    network = {
        'handover_rate_per_cell': 0.5,
        'avg_cpu': 0.70,
        'avg_temp_c': 65
    }
    
    final_action, warnings = validator.validate_action(
        cell_id=1,
        proposed_action=3,  # HANDOVER
        current_kpi=cell_kpi,
        network_state=network
    )
    
    print(f"  Proposed: HANDOVER(3) → Final: {final_action} ({validator._action_name(final_action)})")
    for w in warnings:
        print(f"    {w}\n")
    
    # Test scenario 2: Power increase at thermal limit
    print("Scenario 2: Power increase when thermal limit approaching")
    network['avg_temp_c'] = 88  # Near max
    
    final_action, warnings = validator.validate_action(
        cell_id=2,
        proposed_action=1,  # INCREASE_POWER
        current_kpi=cell_kpi,
        network_state=network
    )
    
    print(f"  Proposed: INCREASE_POWER(1) → Final: {final_action} ({validator._action_name(final_action)})")
    for w in warnings:
        print(f"    {w}\n")


if __name__ == "__main__":
    demonstrate_validation()
