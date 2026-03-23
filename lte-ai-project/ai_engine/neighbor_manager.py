"""
NeighborManager: Cross-cell awareness for intelligent load balancing.

LTE networks consist of interconnected cells with:
- Overlapping coverage areas
- Inter-cell interference
- Neighbor cell load relationships
- Handover optimization between neighbors

This module:
1. Defines neighbor topology
2. Augments features with neighbor KPI
3. Enables load-balancing decisions
4. Provides multi-hop neighbor context
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass


@dataclass
class NeighborTopology:
    """Defines physical adjacency between cells in the network."""
    
    # Standard 6-cell cluster topology (typical for LTE deployments)
    # Cell arrangement:
    #     1 - 2
    #    / \ /
    #   6 - 0 - 3
    #    \ / \
    #     5 - 4
    #
    # Or more commonly: hexagonal grid where each covers ~3 neighbors
    
    # Neighbors per cell (1-indexed cell IDs)
    neighbors = {
        1: [2, 6, 0],      # Cell 1's neighbors
        2: [1, 3, 0],      # Cell 2's neighbors (0 = unknown/undefined)
        3: [2, 4, 0],      # Etc.
        4: [3, 5, 0],
        5: [4, 6, 0],
        6: [5, 1, 0],
    }
    
    # Cell-to-cell proximity (0-1, affects interference and handover)
    proximity = {
        (1, 2): 0.9,   # Neighbors have high proximity
        (1, 6): 0.9,
        (2, 3): 0.9,
        (3, 4): 0.9,
        (4, 5): 0.9,
        (5, 6): 0.9,
        (1, 3): 0.5,   # 2-hop neighbors have medium proximity
        (2, 4): 0.5,
        (3, 5): 0.5,
        (4, 6): 0.5,
        (5, 1): 0.5,
        (6, 2): 0.5,
    }


class NeighborManager:
    """
    Manages neighbor relationships and augmented features.
    
    Transforms:
    - Input: 42 features (7 metrics × 6 cells)
    - Output: 54+ features (includes neighbor metrics)
    """
    
    def __init__(self, topology: NeighborTopology = None):
        """Initialize with network topology."""
        self.topology = topology or NeighborTopology()
        self.base_metrics = [
            "throughput", "delay", "packet_loss", "ue_count",
            "rsrp", "sinr", "cell_load"
        ]
        self.num_cells = 6
    
    def augment_features(self, base_features: np.ndarray) -> np.ndarray:
        """
        Augment base KPI features with neighbor information.
        
        Input shape: (n_samples, 42) - 7 metrics × 6 cells
        Output shape: (n_samples, 54+) - base + neighbor metrics
        
        New features per cell:
        - avg_neighbor_load: Average load of neighboring cells
        - min_neighbor_delay: Minimum delay among neighbors (best option)
        - max_neighbor_sinr: Maximum SINR among neighbors
        - neighbor_count: How many active neighbors
        - load_imbalance: Difference between cell load and neighbor avg
        """
        augmented_list = []
        
        for sample_idx in range(base_features.shape[0]):
            sample = base_features[sample_idx]
            
            # Parse base features into per-cell dicts
            cell_metrics = self._parse_sample(sample)
            
            # Extract base features
            base = sample.copy()
            
            # Calculate neighbor features
            neighbor_features = []
            for cell_id in range(1, self.num_cells + 1):
                neighbor_feats = self._calculate_neighbor_features(
                    cell_id, cell_metrics
                )
                neighbor_features.extend(neighbor_feats)
            
            # Combine: [base_42 + neighbor_features_12]
            augmented = np.concatenate([base, neighbor_features])
            augmented_list.append(augmented)
        
        return np.array(augmented_list)
    
    def _parse_sample(self, sample: np.ndarray) -> Dict[int, Dict[str, float]]:
        """Parse 42-feature vector into per-cell metric dictionary."""
        cells = {}
        
        for cell_id in range(1, self.num_cells + 1):
            cell_idx = (cell_id - 1) * 7  # 7 metrics per cell
            
            cells[cell_id] = {
                'throughput': sample[cell_idx],
                'delay': sample[cell_idx + 1],
                'packet_loss': sample[cell_idx + 2],
                'ue_count': sample[cell_idx + 3],
                'rsrp': sample[cell_idx + 4],
                'sinr': sample[cell_idx + 5],
                'cell_load': sample[cell_idx + 6]
            }
        
        return cells
    
    def _calculate_neighbor_features(self, cell_id: int, 
                                     cell_metrics: Dict[int, Dict]) -> List[float]:
        """
        Calculate augmented features for a cell based on neighbors.
        
        Returns 2 features per neighbor relationship tracking:
        1. Average neighbor load
        2. Min neighbor service time
        3. Max neighbor signal strength
        4. Load imbalance ratio
        """
        
        neighbor_ids = self.topology.neighbors.get(cell_id, [])
        valid_neighbors = [n for n in neighbor_ids if n > 0]  # Filter undefined
        
        if not valid_neighbors:
            return [0.0, 999.0, -150.0, 0.0]  # Defaults
        
        neighbor_data = [cell_metrics[n] for n in valid_neighbors]
        
        # Feature 1: Average neighbor load
        avg_neighbor_load = np.mean([n['cell_load'] for n in neighbor_data])
        
        # Feature 2: Min neighbor delay (best option to handover to)
        min_neighbor_delay = np.min([n['delay'] for n in neighbor_data])
        
        # Feature 3: Max neighbor SINR (quality indicator)
        max_neighbor_sinr = np.max([n['sinr'] for n in neighbor_data])
        
        # Feature 4: Load imbalance (this cell vs neighbors)
        cell_load = cell_metrics[cell_id]['cell_load']
        load_imbalance = cell_load - avg_neighbor_load
        
        return [avg_neighbor_load, min_neighbor_delay, max_neighbor_sinr, load_imbalance]
    
    def get_augmented_feature_names(self) -> List[str]:
        """Get names for all features after augmentation."""
        names = []
        
        # Base features
        for cell_id in range(1, self.num_cells + 1):
            for metric in self.base_metrics:
                names.append(f"{metric}_cell{cell_id}")
        
        # Neighbor features
        for cell_id in range(1, self.num_cells + 1):
            names.append(f"avg_neighbor_load_cell{cell_id}")
            names.append(f"min_neighbor_delay_cell{cell_id}")
            names.append(f"max_neighbor_sinr_cell{cell_id}")
            names.append(f"load_imbalance_cell{cell_id}")
        
        return names
    
    def load_balance_score(self, cell_metrics: Dict[int, Dict]) -> Dict[int, float]:
        """
        Calculate load balance quality per cell.
        
        Score = 1.0: Perfectly balanced with neighbors
        Score = 0.0: Severely imbalanced
        
        Returns dict of {cell_id: score}
        """
        scores = {}
        
        for cell_id in range(1, self.num_cells + 1):
            neighbor_ids = self.topology.neighbors.get(cell_id, [])
            valid_neighbors = [n for n in neighbor_ids if n > 0]
            
            if not valid_neighbors:
                scores[cell_id] = 0.5  # Unknown
                continue
            
            cell_load = cell_metrics[cell_id]['cell_load']
            neighbor_loads = [cell_metrics[n]['cell_load'] for n in valid_neighbors]
            
            # Calculate imbalance as standard deviation
            all_loads = [cell_load] + neighbor_loads
            load_std = np.std(all_loads)
            
            # Convert to score (lower std = higher balance = higher score)
            # Max reasonable imbalance: 0.5 (50% difference)
            balance_score = max(0.0, 1.0 - (load_std / 0.5))
            scores[cell_id] = balance_score
        
        return scores
    
    def find_best_handover_targets(self, cell_id: int, 
                                   cell_metrics: Dict[int, Dict],
                                   max_targets: int = 3) -> List[Tuple[int, float]]:
        """
        Find best neighbor cells for handover.
        
        Ranking criteria:
        1. Lower load (space to accept UEs)
        2. Better signal (SINR)
        3. Lower delay
        4. Proximity (prefer closer neighbors)
        
        Returns:
            List of (neighbor_id, handover_score) sorted by score
        """
        neighbor_ids = self.topology.neighbors.get(cell_id, [])
        valid_neighbors = [n for n in neighbor_ids if n > 0]
        
        candidates = []
        
        for neighbor_id in valid_neighbors:
            neighbor = cell_metrics[neighbor_id]
            proximity = self.topology.proximity.get((cell_id, neighbor_id), 0.5)
            
            # Scoring: lower load is better, higher SINR is better
            load_score = 1.0 - neighbor['cell_load']  # 0-1 (1=empty, 0=full)
            sinr_score = min(1.0, (neighbor['sinr'] + 10) / 25)  # Normalized 0-1
            delay_score = 1.0 - min(1.0, neighbor['delay'] / 100)  # Lower delay is better
            
            # Weighted combined score
            handover_score = (
                0.5 * load_score +      # Load is most important
                0.3 * sinr_score +      # Signal quality matters
                0.1 * delay_score +     # Delay impacts decision
                0.1 * proximity         # Prefer closer neighbors
            )
            
            candidates.append((neighbor_id, handover_score))
        
        # Sort by score (descending) and return top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:max_targets]
    
    def analyze_multi_cell_load(self, cell_metrics: Dict[int, Dict]) -> Dict:
        """Analyze load distribution across all cells."""
        loads = [cell_metrics[i]['cell_load'] for i in range(1, self.num_cells + 1)]
        
        return {
            'mean_load': float(np.mean(loads)),
            'max_load': float(np.max(loads)),
            'min_load': float(np.min(loads)),
            'load_std': float(np.std(loads)),
            'load_variance': float(np.var(loads)),
            'imbalance_ratio': float(np.max(loads) - np.min(loads)),
            'cells_overloaded': sum(1 for l in loads if l > 0.85),
            'cells_underutilized': sum(1 for l in loads if l < 0.30),
        }
    
    def recommend_load_rebalancing(self, cell_metrics: Dict[int, Dict]) -> Dict[int, str]:
        """
        Recommend actions per cell for load balance.
        
        Returns:
            Dict of {cell_id: recommendation}
        """
        recommendations = {}
        analysis = self.analyze_multi_cell_load(cell_metrics)
        
        if analysis['imbalance_ratio'] < 0.15:
            # Well balanced - maintain
            for cell_id in range(1, self.num_cells + 1):
                recommendations[cell_id] = "BALANCE"
            return recommendations
        
        # Unbalanced - recommend handovers from overloaded to underloaded
        loads = {i: cell_metrics[i]['cell_load'] for i in range(1, self.num_cells + 1)}
        
        for cell_id, load in loads.items():
            if load > 0.85:
                # Overloaded - find neighbor to handover to
                targets = self.find_best_handover_targets(cell_id, cell_metrics)
                if targets:
                    best_target = targets[0][0]
                    recommendations[cell_id] = f"HANDOVER_TO_{best_target}"
                else:
                    recommendations[cell_id] = "INCREASE_POWER"
            
            elif load < 0.30:
                # Underutilized - try to accept from neighbors
                recommendations[cell_id] = "ACCEPT_HANDOVER"
            
            else:
                recommendations[cell_id] = "BALANCE"
        
        return recommendations


def demonstrate_neighbor_manager():
    """Demo of neighbor topology and load balancing."""
    print("=== Neighbor Manager Demo ===\n")
    
    manager = NeighborManager()
    
    # Create sample cell metrics
    cell_metrics = {
        1: {'throughput': 5, 'delay': 40, 'packet_loss': 0.001, 'ue_count': 200,
            'rsrp': -110, 'sinr': 8, 'cell_load': 0.90},
        2: {'throughput': 10, 'delay': 20, 'packet_loss': 0.0005, 'ue_count': 100,
            'rsrp': -100, 'sinr': 15, 'cell_load': 0.40},
        3: {'throughput': 8, 'delay': 30, 'packet_loss': 0.001, 'ue_count': 150,
            'rsrp': -105, 'sinr': 10, 'cell_load': 0.70},
        4: {'throughput': 12, 'delay': 15, 'packet_loss': 0.0002, 'ue_count': 80,
            'rsrp': -95, 'sinr': 18, 'cell_load': 0.35},
        5: {'throughput': 7, 'delay': 35, 'packet_loss': 0.002, 'ue_count': 180,
            'rsrp': -115, 'sinr': 5, 'cell_load': 0.85},
        6: {'throughput': 9, 'delay': 25, 'packet_loss': 0.0008, 'ue_count': 120,
            'rsrp': -108, 'sinr': 12, 'cell_load': 0.55},
    }
    
    # Analyze load balance
    analysis = manager.analyze_multi_cell_load(cell_metrics)
    print("Load Balance Analysis:")
    for key, value in analysis.items():
        print(f"  {key}: {value}")
    
    print("\n Load Balance Scores:")
    scores = manager.load_balance_score(cell_metrics)
    for cell_id, score in scores.items():
        print(f"  Cell {cell_id}: {score:.2f}")
    
    print("\nBest Handover Targets:")
    for cell_id in [1, 5]:  # Overloaded cells
        targets = manager.find_best_handover_targets(cell_id, cell_metrics)
        print(f"  Cell {cell_id} (load {cell_metrics[cell_id]['cell_load']:.2f}): {targets}")
    
    print("\nLoad Rebalancing Recommendations:")
    recs = manager.recommend_load_rebalancing(cell_metrics)
    for cell_id, rec in recs.items():
        print(f"  Cell {cell_id}: {rec}")


if __name__ == "__main__":
    demonstrate_neighbor_manager()
