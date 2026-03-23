"""
StabilityController: Prevents decision oscillation and action spam.

SON systems can suffer from cyclic decision-making:
- Handover from A→B, then immediately B→A (ping-pong)
- Repeated power changes without convergence
- Rapid action switching based on volatile KPI readings

This module enforces:
1. Action cooldowns (min time between changes per cell)
2. Decision stability (don't reverse decisions too quickly)
3. Hysteresis (require threshold crossing to change state)
4. Action aggregation (merge conflicting multi-cell decisions)
"""

import numpy as np
from typing import Dict, List, Tuple, Deque
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from datetime import datetime, timedelta


class Action(IntEnum):
    """SON action codes."""
    BALANCE = 0
    INCREASE_POWER = 1
    REDUCE_POWER = 2
    HANDOVER = 3


@dataclass
class ActionRecord:
    """History of a cell's actions."""
    cell_id: int
    timestamp: float
    action: int
    reason: str = "unknown"


@dataclass
class StabilityConfig:
    """Configuration for stability constraints."""
    
    # Action cooldowns (seconds between same action)
    cooldown_balance = 5.0
    cooldown_increase_power = 30.0
    cooldown_reduce_power = 30.0
    cooldown_handover = 60.0  # Very strict for handover (most disruptive)
    
    # Decision reversal penalty (ms cost to reverse a decision)
    reversal_penalty_ms = 500  # Don't reverse if benefit < 500ms of delay savings
    
    # Hysteresis: require threshold crossing to change
    load_hysteresis = 0.05  # Must drop 5% below threshold to reverse
    delay_hysteresis = 5.0  # Must drop 5ms below threshold to reverse
    
    # Decision window: keep action for minimum duration
    min_action_duration = 10.0  # seconds
    
    # Tracking depth: how many decisions to remember per cell
    history_depth = 100


class StabilityController:
    """
    Enforces stability constraints on SON decisions.
    
    Inputs:
    - Raw action from AI predictor
    - Current KPI state
    - Previous network state
    
    Outputs:
    - Stabilized action (or BALANCE if too risky)
    - Confidence score (0-1)
    - Reason for decision
    """
    
    def __init__(self, num_cells: int = 6, config: StabilityConfig = None):
        """Initialize stability controller."""
        self.num_cells = num_cells
        self.config = config or StabilityConfig()
        
        # Action history per cell (for cooldown enforcement)
        self.action_history: Dict[int, Deque[ActionRecord]] = defaultdict(
            lambda: deque(maxlen=self.config.history_depth)
        )
        
        # Last decision time per cell per action type
        self.last_action_time: Dict[Tuple[int, int], float] = {}
        
        # Current imposed action per cell (to track reversals)
        self.current_action: Dict[int, int] = {i: 0 for i in range(1, num_cells + 1)}
        self.current_action_start_time: Dict[int, float] = {}
        
        # KPI baseline for hysteresis
        self.kpi_baseline: Dict[int, Dict[str, float]] = {}
        
        # Oscillation detection
        self.oscillation_score: Dict[int, float] = {i: 0 for i in range(1, num_cells + 1)}
    
    def apply_stability(self, 
                        proposed_actions: np.ndarray,
                        current_kpi: Dict[int, Dict],
                        timestamp_sec: float) -> Tuple[np.ndarray, Dict]:
        """
        Apply stability constraints to proposed actions.
        
        Args:
            proposed_actions: Array of 6 action codes from AI predictor
            current_kpi: Dict mapping cell_id → {throughput, delay, load, ...}
            timestamp_sec: Simulation time (seconds)
        
        Returns:
            (stabilized_actions, decision_info)
            where decision_info has per-cell reasoning
        """
        stabilized = proposed_actions.copy()
        decision_info = {}
        
        for cell_id in range(1, self.num_cells + 1):
            cell_idx = cell_id - 1
            proposed = proposed_actions[cell_idx]
            kpi = current_kpi.get(cell_id, {})
            
            # Check all stability constraints
            final_action, reason, confidence = self._check_constraints(
                cell_id, proposed, kpi, timestamp_sec
            )
            
            stabilized[cell_idx] = final_action
            decision_info[cell_id] = {
                'proposed': proposed,
                'final': final_action,
                'reason': reason,
                'confidence': confidence,
                'oscillation_score': self.oscillation_score[cell_id]
            }
            
            # Record if action differs from proposed
            if final_action != proposed:
                print(f"  Cell {cell_id}: Blocked action {proposed} ({self._action_name(proposed)}) → "
                      f"{final_action} ({self._action_name(final_action)}) [{reason}]")
        
        return stabilized, decision_info
    
    def _check_constraints(self, 
                          cell_id: int, 
                          proposed: int, 
                          kpi: Dict,
                          timestamp_sec: float) -> Tuple[int, str, float]:
        """Check all stability constraints for a single cell."""
        
        current = self.current_action.get(cell_id, 0)
        
        # 1. Cooldown constraint
        if proposed == current:
            # Same action - check cooldown expiry
            key = (cell_id, proposed)
            last_time = self.last_action_time.get(key, timestamp_sec - 999)
            cooldown = self._get_cooldown(proposed)
            
            if timestamp_sec - last_time < cooldown:
                reason = f"Cooldown active ({cooldown}s, elapsed {timestamp_sec - last_time:.1f}s)"
                confidence = 0.0
                return current, reason, confidence
        
        else:  # Different action - more strict checks
            
            # 2. Decision reversion penalty
            if self._is_reversal(current, proposed):
                # Estimate benefit of reversal
                benefit = self._estimate_benefit(proposed, kpi)
                penalty = self.config.reversal_penalty_ms
                
                if benefit < penalty:
                    reason = f"Reversal penalty too high (benefit {benefit}ms < penalty {penalty}ms)"
                    confidence = 0.1
                    return current, reason, confidence
            
            # 3. Hysteresis check
            if not self._passes_hysteresis(cell_id, proposed, kpi):
                reason = f"Hysteresis check failed (state oscillation detected)"
                self.oscillation_score[cell_id] = min(1.0, self.oscillation_score[cell_id] + 0.1)
                confidence = 0.2
                return current, reason, confidence
            
            # 4. Minimum action duration
            current_start = self.current_action_start_time.get(cell_id, timestamp_sec)
            action_duration = timestamp_sec - current_start
            
            if action_duration < self.config.min_action_duration and current != 0:
                reason = f"Action too short ({action_duration:.1f}s < min {self.config.min_action_duration}s)"
                confidence = 0.3
                return current, reason, confidence
            
            # 5. Cooldown for new action
            key = (cell_id, proposed)
            last_time = self.last_action_time.get(key, timestamp_sec - 999)
            cooldown = self._get_cooldown(proposed)
            
            if timestamp_sec - last_time < cooldown:
                reason = f"New action cooldown ({cooldown}s, elapsed {timestamp_sec - last_time:.1f}s)"
                confidence = 0.4
                return current, reason, confidence
        
        # All constraints passed - accept new action
        self._record_action(cell_id, proposed, timestamp_sec, "passed all constraints")
        self.current_action[cell_id] = proposed
        self.current_action_start_time[cell_id] = timestamp_sec
        self.oscillation_score[cell_id] = max(0, self.oscillation_score[cell_id] - 0.05)
        
        return proposed, "Accepted", 0.95
    
    def _get_cooldown(self, action: int) -> float:
        """Get cooldown period for given action."""
        cooldowns = {
            Action.BALANCE: self.config.cooldown_balance,
            Action.INCREASE_POWER: self.config.cooldown_increase_power,
            Action.REDUCE_POWER: self.config.cooldown_reduce_power,
            Action.HANDOVER: self.config.cooldown_handover,
        }
        return cooldowns.get(action, 10.0)
    
    def _is_reversal(self, current: int, proposed: int) -> bool:
        """Check if proposed action reverses the current one."""
        reversals = {
            (Action.INCREASE_POWER, Action.REDUCE_POWER),
            (Action.REDUCE_POWER, Action.INCREASE_POWER),
            (Action.HANDOVER, Action.BALANCE),
        }
        return (current, proposed) in reversals
    
    def _estimate_benefit(self, action: int, kpi: Dict) -> float:
        """Estimate benefit of taking an action (in milliseconds of delay savings)."""
        benefit = 0.0
        
        delay_ms = kpi.get('delay', 50)
        load = kpi.get('load', 0.5)
        sinr = kpi.get('sinr', 5)
        
        if action == Action.INCREASE_POWER and sinr < 5:
            # Could improve SINR, reduce delay
            benefit = max(0, 5 - sinr) * 10  # ~10ms per dB improvement
        
        elif action == Action.REDUCE_POWER and delay_ms < 30:
            # Power reduction helps only if delay is low (won't help)
            benefit = 0
        
        elif action == Action.HANDOVER and load > 0.8:
            # Handover helps if heavily loaded
            benefit = (load - 0.7) * 100  # Up to 10ms savings at high load
        
        return benefit
    
    def _passes_hysteresis(self, cell_id: int, proposed: int, kpi: Dict) -> bool:
        """Check hysteresis: don't oscillate around threshold."""
        current = self.current_action[cell_id]
        
        # Only relevant when changing actions
        if current == proposed or current == Action.BALANCE:
            return True
        
        # Initialize baseline on first change
        if cell_id not in self.kpi_baseline:
            self.kpi_baseline[cell_id] = kpi.copy()
            return True  # First time - assume valid
        
        baseline = self.kpi_baseline[cell_id]
        
        # Check for oscillation patterns
        if proposed == Action.BALANCE:
            # Returning to balance - need significant improvement
            load_diff = kpi.get('load', 0.5) - baseline.get('load', 0.5)
            delay_diff = kpi.get('delay', 50) - baseline.get('delay', 50)
            
            # Need hysteresis threshold to reduce action
            if load_diff > -self.config.load_hysteresis:
                return False  # Not enough improvement
            if delay_diff > -self.config.delay_hysteresis:
                return False  # Not enough improvement
        
        return True  # Passed hysteresis check
    
    def _record_action(self, cell_id: int, action: int, timestamp: float, reason: str):
        """Record an action in history."""
        record = ActionRecord(
            cell_id=cell_id,
            timestamp=timestamp,
            action=action,
            reason=reason
        )
        self.action_history[cell_id].append(record)
        
        # Update last action time
        key = (cell_id, action)
        self.last_action_time[key] = timestamp
    
    def get_action_history(self, cell_id: int) -> List[Dict]:
        """Get action history for a cell."""
        history = []
        for record in self.action_history[cell_id]:
            history.append({
                'timestamp': record.timestamp,
                'action': record.action,
                'action_name': self._action_name(record.action),
                'reason': record.reason
            })
        return history
    
    def aggregate_multi_cell_actions(self, actions: np.ndarray) -> int:
        """
        Aggregate per-cell actions to network-wide decision.
        
        Rules:
        - HANDOVER (3) highest priority (most disruptive)
        - INCREASE_POWER (1) next
        - REDUCE_POWER (2)
        - BALANCE (0) lowest
        """
        action_counts = np.bincount(actions, minlength=4)
        
        # Majority voting with priority bias
        if action_counts[3] > 0:  # Any handover
            return 3
        elif action_counts[1] > self.num_cells * 0.3:  # >30% recommend power increase
            return 1
        elif action_counts[2] > self.num_cells * 0.3:  # >30% recommend power decrease
            return 2
        else:
            return 0  # Default to balance
    
    @staticmethod
    def _action_name(action: int) -> str:
        """Convert action code to name."""
        names = {0: "BALANCE", 1: "INCREASE_POWER", 2: "REDUCE_POWER", 3: "HANDOVER"}
        return names.get(action, "UNKNOWN")


def demonstrate_stability():
    """Demo of stability controller preventing action spam."""
    print("=== Stability Controller Demo ===\n")
    
    controller = StabilityController(num_cells=6)
    
    # Simulate rapid action oscillation scenario
    timestamp = 0.0
    
    # Proposed by AI: handover every second
    for second in range(1, 6):
        timestamp = float(second)
        proposed_actions = np.array([3, 3, 3, 3, 3, 3])  # Handover everything
        
        current_kpi = {
            i: {'load': 0.8, 'delay': 60, 'sinr': 8}
            for i in range(1, 7)
        }
        
        stabilized, info = controller.apply_stability(proposed_actions, current_kpi, timestamp)
        
        print(f"Time {timestamp}s: Proposed=[{','.join(map(str, proposed_actions))}] "
              f"→ Stabilized=[{','.join(map(str, stabilized))}]")
        print(f"  Most actions blocked by cooldown enforcement\n")


if __name__ == "__main__":
    demonstrate_stability()
