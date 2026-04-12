"""
SmartLabeler: Rule-based optimal action generator for SON (Self-Organizing Network).

This module generates intelligent training labels based on telecom domain knowledge
and network optimization rules, instead of using random or derivative-based labels.

It implements proper SON logic:
- Load balancing between cells
- Power adjustment based on signal quality
- Controlled handovers
- SLA compliance (delay <50ms, loss <1%, throughput target)
- Error awareness: Intelligent responses to detected error patterns
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict, List
from dataclasses import dataclass


@dataclass
class SONRules:
    """Telecom SON policy constraints and thresholds."""
    
    # SLA targets (Service Level Agreement)
    max_delay_ms = 50  # Target: delay < 50ms
    max_packet_loss = 0.01  # Target: loss < 1%
    min_throughput_mbps = 1.0  # Target: throughput > 1 Mbps
    min_sinr_db = 0  # Target: SINR > 0dB
    
    # Load balance thresholds
    target_cell_load = 0.70  # Ideal load 70%
    overload_threshold = 0.85  # Congestion threshold
    underutilized_threshold = 0.30  # Underutilized threshold
    load_imbalance_threshold = 0.25  # Max difference between neighbors
    
    # Power management
    max_power_level = 46  # dBm (typical eNodeB)
    min_power_level = 20  # dBm (to avoid excessive coverage)
    rsrp_power_adjustment_threshold = -130  # dBm (when to increase power)
    
    # Handover policy
    sinr_handover_threshold = -5  # dB (SINR below this → consider handover)
    target_neighbor_load = 0.60  # When handing over, prefer neighbors at this load
    max_handovers_per_second = 2  # Prevent handover spam
    
    # Action costs (for decision making)
    cost_balance = 0.1  # Prefer stable state
    cost_power_increase = 0.5  # Moderate cost
    cost_power_decrease = 0.3  # Slightly cheaper than increase
    cost_handover = 2.0  # Expensive (disruptive)


class ErrorDetector:
    """
    **ERROR AWARENESS MODULE**: Detects anomalous patterns indicating errors.
    
    Maps 8 error types to observable KPI signatures:
    - CONGESTION: High load, queue delay, packet loss
    - UNDERUTILIZATION: Low load, low traffic
    - INTERFERENCE: Degraded SINR, high packet loss, low throughput
    - EQUIPMENT_DEGRADATION: Consistent throughput reduction, increased delay
    - JAMMING: Severe SINR/RSRP degradation, high loss
    - DDOS: Extremely high delay, massive packet loss, network load spike
    - WEATHER: RSRP/SINR degradation (but geographically correlated)
    - HANDOVER_FAILURE: Packet loss spikes, sudden delay increases
    """
    
    @staticmethod
    def detect_errors(cell: Dict) -> List[str]:
        """
        Detect likely error types from cell KPI patterns.
        
        Returns:
            List of detected error types (can be multiple)
        """
        detected = []
        
        # DDOS: Extreme delay + extreme packet loss
        if cell['delay'] > 200 and cell['packet_loss'] > 0.30:
            detected.append('DDOS')
        
        # JAMMING: Severe signal degradation + very high loss
        if cell['sinr'] < -15 and cell['rsrp'] < -130 and cell['packet_loss'] > 0.40:
            detected.append('JAMMING')
        
        # CONGESTION: High load + degraded throughput + queuing
        if cell['cell_load'] > 0.85 and cell['throughput'] < 5 and cell['delay'] > 80:
            detected.append('CONGESTION')
        
        # UNDERUTILIZATION: Low load + low traffic
        if cell['cell_load'] < 0.3 and cell['ue_count'] < 50:
            detected.append('UNDERUTILIZATION')
        
        # INTERFERENCE: Moderate signal loss + packet loss
        if -110 > cell['rsrp'] > -125 and 0.1 < cell['packet_loss'] < 0.3:
            detected.append('INTERFERENCE')
        
        # EQUIPMENT_DEGRADATION: Consistent throughput degradation + delay
        if cell['throughput'] < 3 and cell['delay'] > 60:
            detected.append('EQUIPMENT_DEGRADATION')
        
        # WEATHER: SINR+RSRP degradation without extreme loss (unlike jamming)
        if cell['sinr'] < 0 and cell['rsrp'] < -120 and cell['packet_loss'] < 0.2:
            detected.append('WEATHER')
        
        # HANDOVER_FAILURE: Sudden loss spikes + delay increase
        if cell['packet_loss'] > 0.15 and cell['delay'] > 70:
            detected.append('HANDOVER_FAILURE')
        
        return detected


class SONRules:
    """Standard SON rules for network optimization."""
    pass


class SmartLabeler:
    """
    Generates optimal SON actions based on network state and telecom rules.
    
    Output actions per cell:
    - 0: BALANCE (load balance with neighbors)
    - 1: INCREASE_POWER (improve signal coverage)
    - 2: REDUCE_POWER (manage interference)
    - 3: HANDOVER (offload to neighbor)
    """
    
    def __init__(self, rules: SONRules = None):
        """Initialize with optional custom SON rules."""
        self.rules = rules or SONRules()
        self.num_cells = 6
        self.feature_names = [
            "throughput", "delay", "packet_loss", "ue_count",
            "rsrp", "sinr", "cell_load"
        ]
    
    def generate_labels(self, df: pd.DataFrame) -> np.ndarray:
        """
        Convert raw KPI data to optimal SON action labels.
        
        Args:
            df: DataFrame with KPI columns (Th_ENB1-6, Delay_ENB1-6, etc.)
        
        Returns:
            Array of shape (n_samples, 6) with action per cell, or (n_samples,) 
            for single aggregated action
        """
        labels_list = []
        
        for idx, row in df.iterrows():
            # Extract metrics per cell
            cells_state = self._extract_cell_states(row)
            
            # Calculate optimal action per cell (or aggregated)
            actions = self._calculate_optimal_actions(cells_state)
            
            # Aggregate to single label (most urgent action wins)
            aggregated_label = self._aggregate_actions(actions)
            labels_list.append(aggregated_label)
        
        return np.array(labels_list)
    
    def _extract_cell_states(self, row: pd.Series) -> List[Dict]:
        """
        Extract metrics for each cell.
        
        Returns:
            List of 6 dicts, each with {throughput, delay, loss, ue_count, rsrp, sinr, load}
        """
        cells = []
        
        for cell_id in range(1, self.num_cells + 1):
            cell_state = {
                'cell_id': cell_id,
                'throughput': row.get(f'Th_ENB{cell_id}', 0),
                'delay': row.get(f'Delay_ENB{cell_id}', 50),
                'packet_loss': row.get(f'Loss_ENB{cell_id}', 0),
                'ue_count': int(row.get(f'UE_ENB{cell_id}', 0)),
                'rsrp': row.get(f'RSRP_ENB{cell_id}', -100),
                'sinr': row.get(f'SINR_ENB{cell_id}', 15),
                'cell_load': row.get(f'Load_ENB{cell_id}', 0.5)
            }
            cells.append(cell_state)
        
        return cells
    
    def _calculate_optimal_actions(self, cells_state: List[Dict]) -> np.ndarray:
        """
        Determine optimal action for each cell.
        
        Strategy (priority order):
        1. If SLA violated (high delay/loss) + neighbors available → HANDOVER
        2. If congested (load >85%) + neighbors available → HANDOVER for load balance
        3. If poor signal (RSRP <-130) + power available → INCREASE_POWER
        4. If underutilized (load <30%) + high signal → REDUCE_POWER for efficiency
        5. Otherwise → BALANCE (maintain state)
        
        Returns:
            Array of 6 action values (0-3 per cell)
        """
        actions = np.zeros(self.num_cells, dtype=int)
        
        for i, cell in enumerate(cells_state):
            action = self._decide_cell_action(cell, cells_state)
            actions[i] = action
        
        return actions
    
    def _decide_cell_action(self, cell: Dict, all_cells: List[Dict]) -> int:
        """Decide optimal action for a single cell.
        
        **CRITICAL FIX**: Now includes error awareness to handle error scenarios properly.
        """
        
        # **NEW**: Detect errors to understand root cause of degradation
        detected_errors = ErrorDetector.detect_errors(cell)
        
        # If errors detected, apply specialized response logic
        if detected_errors:
            return self._decide_action_with_errors(cell, all_cells, detected_errors)
        
        # Original logic for non-error cases
        # SLA Violation → Consider handover
        sla_violated = (
            cell['delay'] > self.rules.max_delay_ms or
            cell['packet_loss'] > self.rules.max_packet_loss or
            cell['throughput'] < self.rules.min_throughput_mbps
        )
        
        if sla_violated and cell['ue_count'] > 0:
            # Check if neighbor with better conditions exists
            best_neighbor = self._find_best_neighbor(cell, all_cells)
            severe_sla = (cell['delay'] > 100 or cell['packet_loss'] > 0.05)
            neighbor_can_help = best_neighbor and (best_neighbor['cell_load'] < max(0.65, cell['cell_load'] - 0.20))
            if severe_sla and neighbor_can_help:
                return 3  # HANDOVER
        
        # Congestion → Load balance via handover
        if cell['cell_load'] > self.rules.overload_threshold and cell['ue_count'] > 0:
            best_neighbor = self._find_best_neighbor(cell, all_cells)
            if best_neighbor and best_neighbor['cell_load'] < max(0.65, cell['cell_load'] - 0.20):
                return 3  # HANDOVER to lighter cell
        
        # Poor signal → Increase power
        if cell['rsrp'] < self.rules.rsrp_power_adjustment_threshold or cell['sinr'] < self.rules.min_sinr_db:
            if cell['cell_load'] < 0.85:
                return 1  # INCREASE_POWER
        
        # Excessive power → Reduce for efficiency
        if cell['sinr'] > 15 and cell['cell_load'] < self.rules.underutilized_threshold:
            if cell['ue_count'] < 80:
                return 2  # REDUCE_POWER
        
        # Default: maintain balance
        return 0  # BALANCE
    
    def _decide_action_with_errors(self, cell: Dict, all_cells: List[Dict], errors: List[str]) -> int:
        """
        Specialized decision logic when errors are detected.
        
        Error→Action Mapping (8 QoS factors):
        - CONGESTION → HANDOVER (offload users to neighbors)
        - UNDERUTILIZATION → REDUCE_POWER (save energy)
        - INTERFERENCE → REDUCE_POWER (reduce noise generation)
        - EQUIPMENT_DEGRADATION → HANDOVER (failover users)
        - JAMMING → HANDOVER + REDUCE_POWER (get away from attacker)
        - DDOS → HANDOVER (distribute load, network-wide action)
        - WEATHER → INCREASE_POWER (fight attenuation)
        - HANDOVER_FAILURE → BALANCE (stabilize, avoid cascading failures)
        """
        action_scores = np.zeros(4)  # Score for each action: [0=BALANCE, 1=INCREASE_POWER, 2=REDUCE_POWER, 3=HANDOVER]
        
        for error_type in errors:
            if error_type == 'CONGESTION':
                # Try to offload congested cell
                action_scores[3] += 2.0  # Strong preference for HANDOVER
            
            elif error_type == 'UNDERUTILIZATION':
                # Reduce power to save resources
                action_scores[2] += 1.5  # REDUCE_POWER
            
            elif error_type == 'INTERFERENCE':
                # Reduce power to minimize interference generation
                action_scores[2] += 2.0  # REDUCE_POWER
            
            elif error_type == 'EQUIPMENT_DEGRADATION':
                # Equipment is failing, offload users
                action_scores[3] += 2.0  # HANDOVER (failover)
            
            elif error_type == 'JAMMING':
                # Under attack: reduce power, consider handover
                action_scores[2] += 1.5  # Reduce power
                action_scores[3] += 1.5  # Also consider handover
            
            elif error_type == 'DDOS':
                # Network-wide attack: redistribute load
                action_scores[3] += 3.0  # Strong HANDOVER (distribute attack load)
            
            elif error_type == 'WEATHER':
                # Environmental degradation: increase power to fight attenuation
                action_scores[1] += 2.0  # INCREASE_POWER
            
            elif error_type == 'HANDOVER_FAILURE':
                # Stability is key during handover failures
                action_scores[0] += 1.0  # BALANCE (avoid further disruption)
        
        # Choose action with highest score
        best_action = int(np.argmax(action_scores))
        
        # Safety check: only execute handover if neighbor available
        if best_action == 3 and not self._find_best_neighbor(cell, all_cells):
            # No good neighbor, fall back to power adjustment
            if 'WEATHER' in errors:
                return 1  # INCREASE_POWER for weather
            else:
                return 2  # REDUCE_POWER for other interference
        
        return best_action
    
    def _find_best_neighbor(self, cell: Dict, all_cells: List[Dict]) -> Dict:
        """
        Find best neighbor cell for handover.
        
        - Lower load preferred
        - Good signal (SINR > 5) required
        - Different cell than current
        
        Returns:
            Best neighbor dict or None
        """
        neighbors = []
        
        for neighbor in all_cells:
            if neighbor['cell_id'] == cell['cell_id']:
                continue
            
            # Must have good enough signal
            if neighbor['sinr'] < 5:
                continue
            
            # Must not be fully congested
            if neighbor['cell_load'] > self.rules.overload_threshold:
                continue
            
            neighbors.append(neighbor)
        
        if not neighbors:
            return None
        
        # Choose with minimum load
        return min(neighbors, key=lambda x: x['cell_load'])
    
    def _aggregate_actions(self, actions: np.ndarray) -> int:
        """
        Convert per-cell actions to single network-wide action.
        
        Priority: HANDOVER (3) > INCREASE_POWER (1) > REDUCE_POWER (2) > BALANCE (0)
        """
        counts = np.bincount(actions, minlength=4)
        total = max(1, int(np.sum(counts)))

        # Require meaningful support to avoid handover-dominated labels.
        if counts[3] / total >= 0.34:
            return 3

        if counts[1] / total >= 0.25:
            return 1

        if counts[2] / total >= 0.25:
            return 2

        # Otherwise keep network in balanced state.
        return 0
    
    def get_per_cell_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate labels with per-cell action breakdown for analysis.
        
        Returns:
            DataFrame with per-cell actions and reasoning
        """
        results = []
        
        for idx, row in df.iterrows():
            cells_state = self._extract_cell_states(row)
            per_cell_actions = []
            
            for i, cell in enumerate(cells_state):
                action = self._decide_cell_action(cell, cells_state)
                per_cell_actions.append({
                    'timestamp': idx,
                    'cell_id': cell['cell_id'],
                    'action': action,
                    'action_name': self._action_name(action),
                    'load': cell['cell_load'],
                    'delay': cell['delay'],
                    'sinr': cell['sinr'],
                    'rsrp': cell['rsrp']
                })
            
            results.extend(per_cell_actions)
        
        return pd.DataFrame(results)
    
    @staticmethod
    def _action_name(action: int) -> str:
        """Convert action code to human-readable name."""
        action_map = {
            0: "BALANCE",
            1: "INCREASE_POWER",
            2: "REDUCE_POWER",
            3: "HANDOVER"
        }
        return action_map.get(action, "UNKNOWN")


def generate_smart_training_labels(training_data_path: str, 
                                   output_path: str = None) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    Convenience function to generate smart labels for entire dataset.
    
    Args:
        training_data_path: Path to training CSV from NS-3
        output_path: Optional path to save analysis DataFrame
    
    Returns:
        (labels_array, analysis_dataframe)
    """
    print(f"Loading training data from {training_data_path}...")
    df = pd.read_csv(training_data_path)
    
    labeler = SmartLabeler()
    print("Generating smart labels based on SON rules...")
    labels = labeler.generate_labels(df)
    
    # Generate analysis
    analysis_df = labeler.get_per_cell_actions(df)
    
    if output_path:
        print(f"Saving analysis to {output_path}...")
        analysis_df.to_csv(output_path, index=False)
    
    # Print statistics
    unique, counts = np.unique(labels, return_counts=True)
    print("\n=== Smart Label Distribution ===")
    for action_code, count in zip(unique, counts):
        action_name = SmartLabeler._action_name(action_code)
        percentage = (count / len(labels)) * 100
        print(f"  {action_name} ({action_code}): {count:4d} ({percentage:5.1f}%)")
    
    return labels, analysis_df


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        training_data_path = sys.argv[1]
        output_analysis = sys.argv[2] if len(sys.argv) > 2 else None
        
        labels, analysis = generate_smart_training_labels(training_data_path, output_analysis)
        print(f"\nGenerated {len(labels)} smart labels")
    else:
        print("Usage: python smart_labeler.py <training_data.csv> [output_analysis.csv]")
