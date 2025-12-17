import csv
import itertools as it
from collections import defaultdict

def load_all_players(csv_filename):
    """
    Load all players from a CSV file with one column (no header).
    Returns a list of player names.
    """
    players = []
    try:
        with open(csv_filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip():  # Skip empty rows
                    players.append(row[0].strip())
    except FileNotFoundError:
        print(f"Warning: File '{csv_filename}' not found. Using empty player list.")
    
    return players

def create_player_pool(active_players):
    """
    Create player pool with reserve players if needed to fill tables of 4.
    Returns: (active_pool, number_of_tables, reserve_players_added)
    """
    number_of_active_players = len(active_players)
    number_of_tables = number_of_active_players // 4
    reserve_players = 0
    active_pool = active_players[:]
    
    # Add reserve players if needed
    if number_of_active_players % 4 != 0:
        number_of_tables += 1
        reserve_players = number_of_tables * 4 - number_of_active_players
        for reserve_player in range(reserve_players):
            active_pool.append(f"Reserve {reserve_player + 1}")
    
    print(f'Aantal tafels: {number_of_tables}')
    print(f'Aangevuld met {reserve_players} reservespelers')
    
    return active_pool, number_of_tables, reserve_players

def load_pair_counts(csv_filename):
    """Load existing pair counts from CSV."""
    pair_counts = defaultdict(int)
    try:
        with open(csv_filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if row:
                    pair = tuple(sorted([row[0], row[1]]))
                    pair_counts[pair] = int(row[2])
    except FileNotFoundError:
        pass
    return pair_counts

def score_group(group, pair_counts):
    """
    Calculate score for a single group using MAX scoring.
    Score = the highest pair count in the group (worst pair).
    Lower score is better - we want to avoid high-count pairs.
    
    Example: If group has pairs with counts [0, 0, 1, 0, 5, 0],
    the score is 5 (the worst pairing in this group).
    """
    pair_scores = [pair_counts.get(tuple(sorted(pair)), 0) 
                   for pair in it.combinations(group, 2)]
    
    # Return the maximum pair count (worst pair) in this group
    # If all pairs are new (count=0), score will be 0 (best possible)
    return max(pair_scores) if pair_scores else 0

def make_groups_greedy(pool, group_size, csv_filename, max_configs=20):
    """
    Generate table configurations greedily, prioritizing unused/low-count pairs.
    
    SCORING METHOD:
    - Each table's score = MAX pair count in that table (worst pairing)
    - Config score = MAX across all tables (worst pair in entire config)
    - Lower score is better - minimizes the worst pairing overall
    
    Returns top configurations sorted by max pair count (lowest first).
    """
    if len(pool) % group_size != 0:
        raise ValueError("Aantal deelnemers is niet deelbaar door de groep grootte")
    
    pair_counts = load_pair_counts(csv_filename)
    configs = []
    
    # Try multiple starting points for diversity
    for seed in range(max_configs * 3):  # Try more to get best 20
        remaining = pool[:]
        config = []
        used_pairs = set()
        
        # Shuffle for different starting points
        import random
        random.seed(seed)
        random.shuffle(remaining)
        
        while remaining:
            best_group = None
            best_score = float('inf')
            
            # Try combinations prioritizing low pair counts
            attempts = 0
            for group in it.combinations(remaining, group_size):
                attempts += 1
                if attempts > 500:  # Limit search
                    break
                
                # Check Reserve constraint
                reserve_count = sum(1 for name in group if "Reserve" in name)
                if reserve_count > 1:
                    continue
                
                # Score = MAX pair count in this group (worst pairing)
                group_score = score_group(group, pair_counts)
                
                # Penalize reusing pairs within this config
                pairs_in_group = set(tuple(sorted(pair)) 
                                    for pair in it.combinations(group, 2))
                overlap = len(pairs_in_group & used_pairs)
                adjusted_score = group_score + (overlap * 100)  # Heavy penalty
                
                if adjusted_score < best_score:
                    best_score = adjusted_score
                    best_group = group
            
            if best_group is None:
                break  # No valid group found
            
            config.append(best_group)
            used_pairs.update(tuple(sorted(pair)) 
                            for pair in it.combinations(best_group, 2))
            remaining = [x for x in remaining if x not in best_group]
        
        if len(config) == len(pool) // group_size:  # Complete config
            # Sort players alphabetically within each group
            sorted_config = [tuple(sorted(g)) for g in config]
            
            # Calculate overall MAX score (worst pair in entire config)
            # Only consider pairs without Reserve players
            max_pair_count = 0
            for group in sorted_config:
                # Only count pairs without Reserve players
                group_pairs = [pair for pair in it.combinations(group, 2)
                              if not any("Reserve" in p for p in pair)]
                if group_pairs:
                    # Max pair count in this group
                    group_max = max(pair_counts.get(tuple(sorted(pair)), 0) 
                                   for pair in group_pairs)
                    # Track the overall maximum across all groups
                    max_pair_count = max(max_pair_count, group_max)
            
            # Score = worst pair count in entire configuration
            configs.append((max_pair_count, sorted_config))
    
    # Remove duplicates and sort by maximum pair count (lowest first)
    unique_configs = []
    seen = set()
    for score, config in sorted(configs, key=lambda x: x[0]):
        # Create hashable representation
        config_key = tuple(sorted(tuple(sorted(g)) for g in config))
        if config_key not in seen:
            seen.add(config_key)
            unique_configs.append((score, config))
            if len(unique_configs) >= max_configs:
                break
    
    return unique_configs[:max_configs]


# Alternative: Pure greedy (fastest, single best solution)
def make_groups_simple_greedy(pool, group_size, csv_filename):
    """
    Single-pass greedy: always pick group with lowest MAX pair count.
    
    SCORING METHOD:
    - Each table's score = MAX pair count in that table (worst pairing)
    - Config score = MAX across all tables (worst pair in entire config)
    - Lower score is better - minimizes the worst pairing overall
    
    Fastest option, returns one good configuration.
    """
    if len(pool) % group_size != 0:
        raise ValueError("Aantal deelnemers is niet deelbaar door de groep grootte")
    
    pair_counts = load_pair_counts(csv_filename)
    remaining = pool[:]
    config = []
    
    while remaining:
        best_group = None
        best_score = float('inf')
        
        for group in it.combinations(remaining, group_size):
            reserve_count = sum(1 for name in group if "Reserve" in name)
            if reserve_count > 1:
                continue
            
            # Score = MAX pair count in this group (worst pairing)
            score = score_group(group, pair_counts)
            if score < best_score:
                best_score = score
                best_group = group
        
        if best_group is None:
            raise ValueError("Kan geen geldige groep vinden")
        
        config.append(best_group)
        remaining = [x for x in remaining if x not in best_group]
    
    # Sort players alphabetically within each group
    sorted_config = [tuple(sorted(g)) for g in config]
    
    # Calculate overall MAX score (worst pair in entire config)
    # Only consider pairs without Reserve players
    max_pair_count = 0
    for group in sorted_config:
        # Only count pairs without Reserve players
        group_pairs = [pair for pair in it.combinations(group, 2)
                      if not any("Reserve" in p for p in pair)]
        if group_pairs:
            # Max pair count in this group
            group_max = max(pair_counts.get(tuple(sorted(pair)), 0) 
                           for pair in group_pairs)
            # Track the overall maximum across all groups
            max_pair_count = max(max_pair_count, group_max)
    
    # Score = worst pair count in entire configuration
    return [(max_pair_count, sorted_config)]


def update_pairs_in_csv(config, csv_filename):
    """
    Update CSV with pairs from the chosen configuration.
    Each group of 4 players generates 6 pairs.
    Skips pairs that include Reserve players.
    """
    # Load existing counts
    pair_counts = load_pair_counts(csv_filename)
    
    # Add pairs from chosen configuration (excluding Reserve players)
    pairs_added = 0
    for group in config:
        for pair in it.combinations(sorted(group), 2):
            # Skip pairs with Reserve players
            if any("Reserve" in player for player in pair):
                continue
            
            pair_key = tuple(sorted(pair))
            pair_counts[pair_key] += 1
            pairs_added += 1
    
    # Write back to CSV
    with open(csv_filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Player1', 'Player2', 'Count'])  # Header
        for (p1, p2), count in sorted(pair_counts.items()):
            writer.writerow([p1, p2, count])
    
    print(f"✓ Updated {csv_filename} with {pairs_added} pairs (Reserve pairs excluded)")