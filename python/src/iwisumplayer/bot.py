import random
from battlecode25.stubs import *

# ===== GLOBALS =====
turn_count = 0
directions = list(Direction)  # All 8 directions
priorities = {
    UnitType.SOLDIER: ["attack", "paint", "ruins"],
    UnitType.MOPPER: ["clean", "attack"],
    UnitType.SPLASHER: ["splash"]  # Placeholder for splash logic
}

# ===== CORE FUNCTIONS =====
def turn():
    """Main turn handler."""
    global turn_count
    turn_count += 1
    
    unit_type = get_type()
    if unit_type.is_tower_type():
        run_tower()
    elif unit_type == UnitType.SOLDIER:
        run_soldier()
    elif unit_type == UnitType.MOPPER:
        run_mopper()
    # Add other unit types as needed

# ===== TOWER LOGIC =====
def run_tower():
    """Smart tower that builds units based on game state."""
    # Build soldiers every 5 turns if possible
    if turn_count % 5 == 0:
        for dir in strategic_directions():
            loc = get_location().add(dir)
            if can_build_robot(UnitType.SOLDIER, loc):
                build_robot(UnitType.SOLDIER, loc)
                break
    
    # Emergency mopper production if enemy paint nearby
    if sense_nearby_paint(3, get_team().opponent()):
        for dir in strategic_directions():
            loc = get_location().add(dir)
            if can_build_robot(UnitType.MOPPER, loc):
                build_robot(UnitType.MOPPER, loc)
                break
    
    # Broadcast enemy sightings
    if enemies := sense_nearby_robots(team=get_team().opponent()):
        broadcast_enemy(enemies[0].get_location())

def strategic_directions():
    """Prioritize directions toward enemy territory."""
    enemy_tower = closest_enemy_structure()
    if enemy_tower:
        base_dir = get_location().direction_to(enemy_tower)
        # Return directions roughly toward enemy
        return [d for d in directions 
                if abs(d.ordinal() - base_dir.ordinal()) <= 2]
    return directions  # Fallback to all directions

# ===== SOLDIER LOGIC =====
def run_soldier():
    """Strategic soldier with objective priorities."""
    for task in priorities[UnitType.SOLDIER]:
        if task == "attack" and handle_combat():
            return
        if task == "ruins" and handle_ruins():
            return
        if task == "paint" and handle_painting():
            return
    
    # Default exploration
    move_toward(closest_enemy_structure() or random_direction())

def handle_combat():
    """Attack nearby enemies or chase if visible."""
    if enemies := sense_nearby_robots(team=get_team().opponent()):
        target = min(enemies, key=lambda e: get_location().distance_to(e.get_location()))
        if can_attack(target.get_location()):
            attack(target.get_location())
            return True
        move_toward(target.get_location())
        return True
    return False

def handle_ruins():
    """Claim ruins for tower construction."""
    if ruins := [tile for tile in sense_nearby_map_infos() if tile.has_ruin()]:
        ruin = min(ruins, key=lambda r: get_location().distance_to(r.get_map_location()))
        return complete_ruin(ruin)
    return False

# ===== MOPPER LOGIC =====
def run_mopper():
    """Efficient cleaner with combat capabilities."""
    # Priority 1: Clean enemy paint
    if enemy_paint := [tile for tile in sense_nearby_map_infos() 
                      if tile.get_paint().is_enemy()]:
        target = max(enemy_paint, key=lambda t: t.get_paint_amount())
        if can_mop_swing(get_location().direction_to(target.get_map_location())):
            mop_swing(dir)
            return
    
    # Priority 2: Attack nearby enemies
    if handle_combat():
        return
    
    # Default: Move toward densest enemy paint
    if enemy_areas := sense_nearby_paint(-1, get_team().opponent()):
        move_toward(enemy_areas[0].get_map_location())

# ===== UTILITIES =====
def move_toward(target_loc):
    """Pathfinding toward a location."""
    if not target_loc:
        return False
    
    best_dir = None
    min_dist = float('inf')
    
    for dir in directions:
        if can_move(dir):
            new_loc = get_location().add(dir)
            dist = new_loc.distance_to(target_loc)
            if dist < min_dist:
                min_dist = dist
                best_dir = dir
    
    if best_dir:
        move(best_dir)
        return True
    return False

def broadcast_enemy(loc):
    """Send enemy location to nearby allies."""
    for ally in sense_nearby_robots(team=get_team()):
        if can_send_message(ally.get_location()):
            send_message(ally.get_location(), f"enemy@{loc.x},{loc.y}")

def closest_enemy_structure():
    """Find nearest enemy tower/ruin."""
    structures = [e for e in sense_nearby_robots(-1) 
                 if e.get_team() == get_team().opponent() and e.get_type().is_tower_type()]
    if structures:
        return min(structures, key=lambda s: get_location().distance_to(s.get_location()))

# ===== PAINTING HELPERS =====
def handle_painting():
    """Paint strategic locations."""
    if not get_location().get_paint().is_ally():
        attack(get_location())
        return True
    
    # Paint toward enemy base
    if enemy_base := closest_enemy_structure():
        dir = get_location().direction_to(enemy_base)
        if can_move(dir) and not get_location().add(dir).get_paint().is_ally():
            move(dir)
            return True
    return False