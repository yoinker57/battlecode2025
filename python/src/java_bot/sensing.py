from battlecode25.stubs import *
from .constants import *
from .map_info_distance_comparator import MapInfoDistanceComparator
import random

class Sensing:
    @staticmethod
    def find_nearest_lowest_hp(rc):
        """Finds the opponent robots within actionRadius with the lowest HP and returns its RobotInfo"""
        nearby_robots = rc.sense_nearby_robots(rc.get_type().action_radius_squared, rc.get_team().opponent())
        target_robot = None
        min_health = -1
        for robot in nearby_robots:
            robot_health = robot.get_health()
            if min_health == -1 or min_health > robot_health:
                target_robot = robot
                min_health = robot_health
        return target_robot

    @staticmethod
    def can_build_tower(rc, tower_location):
        """
        Given the MapLocation of a ruin, check if we can eventually build a tower at the ruin
        Returns False if there is enemy paint, or if there is a tower already existing
        Purpose: Check if we should go to this ruin to build on it
        """
        for pattern_tile in rc.sense_nearby_map_infos(tower_location, 8):
            if pattern_tile.has_ruin():
                if rc.can_sense_robot_at_location(pattern_tile.get_map_location()):
                    return False
            elif pattern_tile.get_paint().is_enemy():
                return False
        return True

    @staticmethod
    def find_any_ruin(rc, robot_location, nearby_tiles):
        """
        Finds the closest ruin that fits the following criteria
        1. No tower at the ruin
        2. No ally robots directly adjacent to the ruin
        """
        cur_ruin = None
        min_dis = -1
        for tile in nearby_tiles:
            if tile.has_ruin():
                tile_location = tile.get_map_location()
                if (not rc.can_sense_robot_at_location(tile_location) and 
                    len(rc.sense_nearby_robots(tile_location, 2, rc.get_team())) < 1):
                    ruin_distance = robot_location.distance_squared_to(tile_location)
                    if min_dis == -1 or min_dis > ruin_distance:
                        cur_ruin = tile
                        min_dis = ruin_distance
        return cur_ruin

    @staticmethod
    def find_best_ruin(rc, robot_location, nearby_tiles):
        """
        Finds the closest ruin that fits the following criteria
        1. No enemy paint around the tower
        2. No tower at the ruin
        3. No ally robots directly adjacent to the ruin
        """
        cur_ruin = None
        min_dis = -1
        for tile in nearby_tiles:
            if tile.has_ruin():
                tile_location = tile.get_map_location()
                if (not rc.can_sense_robot_at_location(tile_location) and 
                    Sensing.can_build_tower(rc, tile_location) and
                    len(rc.sense_nearby_robots(tile_location, 2, rc.get_team())) < 1):
                    ruin_distance = robot_location.distance_squared_to(tile_location)
                    if min_dis == -1 or min_dis > ruin_distance:
                        cur_ruin = tile
                        min_dis = ruin_distance
        return cur_ruin

    @staticmethod
    def find_paintable_tile(rc, location, range_squared):
        """
        Finds a paintable tile that is within a specific range of location and returns the MapInfo of that tile
        Paintable: empty paint or incorrect allied paint
        If none are found, return null
        """
        for pattern_tile in rc.sense_nearby_map_infos(location, range_squared):
            if (rc.can_paint(pattern_tile.get_map_location()) and
                (pattern_tile.get_paint() == PaintType.EMPTY or
                 pattern_tile.get_mark() != pattern_tile.get_paint() and pattern_tile.get_mark() != PaintType.EMPTY)):
                return pattern_tile
        return None

    @staticmethod
    def find_paintable_ruin_tile(rc, ruin_location, ruin_pattern):
        """
        Finds a paintable tile that is within a specific range of tower and returns the MapInfo of that tile
        Paintable: tile with paint different than needed
        If none are found, return null
        """
        # Iterate through the 5x5 area around a ruin
        for i in range(-2, 3):
            for j in range(-2, 3):
                pattern_tile = ruin_location.translate(i, j)
                if rc.can_paint(pattern_tile) and ruin_pattern[i+2][j+2] != rc.sense_map_info(pattern_tile).get_paint():
                    return [i, j]
        return None

    @staticmethod
    def get_movable_empty_tiles(rc):
        """
        Finds tiles adjacent to rc that
        1. Can be moved to
        2. Have no paint on them
        3. Hasn't been at this tile in the last 8 tiles it has moved to
        Returns a list of MapInfo for these tiles
        """
        adjacent_tiles = rc.sense_nearby_map_infos(2)
        valid_adjacent = []
        for adjacent_tile in adjacent_tiles:
            if (adjacent_tile.get_paint() == PaintType.EMPTY and 
                adjacent_tile.is_passable() and
                adjacent_tile.get_map_location() not in globals()['last8']):
                valid_adjacent.append(adjacent_tile)
        return valid_adjacent

    @staticmethod
    def get_movable_painted_tiles(rc):
        """
        Finds tiles adjacent to rc that
        1. Can be moved to
        2. Has paint on them
        3. Hasn't been at this tile in the last 8 tiles it has moved to
        Returns a list of MapInfo for these tiles
        """
        adjacent_tiles = rc.sense_nearby_map_infos(2)
        valid_adjacent = []
        for adjacent_tile in adjacent_tiles:
            if (adjacent_tile.get_paint().is_ally() and 
                adjacent_tile.is_passable() and
                adjacent_tile.get_map_location() not in globals()['last8']):
                valid_adjacent.append(adjacent_tile)
        return valid_adjacent

    @staticmethod
    def tower_in_range(rc, range_val, ally=None):
        """
        Returns RobotInfo of a tower if there is a tower with a range of radius
        ally = True: search for allied towers, and vice versa
        If ally is not passed, then we search for all towers
        Returns None if no tower is within range
        """
        if ally is None:
            robots_in_range = rc.sense_nearby_robots(range_val)
        else:
            team = rc.get_team() if ally else rc.get_team().opponent()
            robots_in_range = rc.sense_nearby_robots(range_val, team)
            
        for robot in robots_in_range:
            if robot.get_type().is_tower_type():
                return robot
        return None

    @staticmethod
    def find_enemy_paint(rc, nearby_tiles):
        """Returns map info of location of enemy paint"""
        for tile in nearby_tiles:
            if tile.get_paint().is_enemy():
                return tile
        return None

    @staticmethod
    def count_empty_around(rc, center):
        """Counts the number of empty, passable tiles in a 3x3 area centered at center, assuming it is all visible"""
        surrounding_tiles = rc.sense_nearby_map_infos(center, 2)
        count = 0
        for surrounding_tile in surrounding_tiles:
            if (surrounding_tile.get_paint() == PaintType.EMPTY and 
                surrounding_tile.is_passable() and
                not rc.can_sense_robot_at_location(surrounding_tile.get_map_location())):
                count += 1
        return count

    @staticmethod
    def is_robot(rc, robot_id):
        """Checks if a Robot is a robot by ID"""
        if rc.can_sense_robot(robot_id):
            bot = rc.sense_robot(robot_id)
            return bot.get_type().is_robot_type()
        return False

    @staticmethod
    def is_tower(rc, robot_id):
        """Checks if a Robot is a tower by ID"""
        if rc.can_sense_robot(robot_id):
            bot = rc.sense_robot(robot_id)
            return bot.get_type().is_tower_type()
        return False

    @staticmethod
    def get_near_by_enemies_sorted_shuffled(rc):
        """Get nearby enemies sorted by distance"""
        nearby_enemies = []
        enemies = list(rc.sense_nearby_map_infos())
        for enemy in enemies:
            if enemy.get_paint().is_enemy():
                nearby_enemies.append(enemy)
            if enemy.get_paint() == PaintType.EMPTY and not enemy.has_ruin() and not enemy.is_wall():
                globals()['fill_empty'] = enemy
        if not nearby_enemies:
            return None
        return max(nearby_enemies, key=lambda x: MapInfoDistanceComparator(rc)(x, x))

    @staticmethod
    def score_splasher_tiles(rc):
        """Scores tiles that decides where a splasher should go"""
        nearby_tiles = rc.sense_nearby_map_infos()
        # hash the tiles
        for tile in nearby_tiles:
            loc = tile.get_map_location()
            paint = tile.get_paint()
            if paint is None:
                continue

            if paint == PaintType.EMPTY and tile.is_passable():
                globals()['curr_grid'][loc.x][loc.y] = 0
            elif paint.is_enemy():
                globals()['curr_grid'][loc.x][loc.y] = 2
            elif paint.is_ally():
                globals()['curr_grid'][loc.x][loc.y] = -1
            else:
                globals()['curr_grid'][loc.x][loc.y] = -1

        best = None
        best_score = -1
        for tile in nearby_tiles:
            if tile.is_passable() and rc.can_attack(tile.get_map_location()):
                score = Sensing.score_splash(rc, tile)
                if score > best_score:
                    best_score = score
                    best = tile

        if best is None:
            x = rc.get_location().x
            y = rc.get_location().y
            for dx, dy in [(0, 4), (4, 0), (0, -4), (-4, 0)]:
                if 0 <= x + dx < rc.get_map_width() and 0 <= y + dy < rc.get_map_height():
                    tile = rc.sense_map_info(rc.get_location().translate(dx, dy))
                    score = Sensing.score_splash(rc, tile)
                    if score > best_score:
                        best_score = score
                        best = tile
        return best

    @staticmethod
    def score_splash(rc, tile):
        """Scores based on paintTypes of tiles within splasher radius"""
        out = 0
        loc = tile.get_map_location()
        x = loc.x
        y = loc.y
        up = rc.get_map_height()
        right = rc.get_map_width()

        # Check all tiles in splash radius
        splash_coords = [
            (x, y-2), (x-1, y-1), (x, y-1), (x+1, y-1),
            (x-2, y), (x-1, y), (x, y), (x+1, y), (x+2, y),
            (x-1, y+1), (x, y+1), (x+1, y+1), (x, y+2)
        ]

        for tx, ty in splash_coords:
            if 0 <= tx < right and 0 <= ty < up:
                out += globals()['curr_grid'][tx][ty]

        return out

    @staticmethod
    def is_in_defense_range(rc, ruin_loc):
        """Checks whether a ruin is in the middle area of the map, in which a defense tower is built"""
        x_lower = int(rc.get_map_width() * DEFENSE_RANGE)
        y_lower = int(rc.get_map_height() * DEFENSE_RANGE)
        x_higher = int(rc.get_map_width() * (1 - DEFENSE_RANGE))
        y_higher = int(rc.get_map_height() * (1 - DEFENSE_RANGE))
        x = ruin_loc.x
        y = ruin_loc.y
        return x_lower <= x <= x_higher and y_lower <= y <= y_higher

    @staticmethod
    def score_tile(rc, tile, care_about_enemy):
        """Score a tile based on various factors"""
        surrounding_tiles = rc.sense_nearby_map_infos(tile, 2)
        count = 30
        for surrounding_tile in surrounding_tiles:
            if surrounding_tile.get_paint().is_enemy() and care_about_enemy:
                count += 5
            if surrounding_tile.get_paint() == PaintType.EMPTY and surrounding_tile.is_passable():
                count += 3
            if not surrounding_tile.is_passable():
                count -= 2
            surrounding_location = surrounding_tile.get_map_location()
            if rc.can_sense_robot_at_location(surrounding_location):
                if rc.sense_robot_at_location(surrounding_location).get_team() == rc.get_team():
                    count -= 3
        return count

    @staticmethod
    def conflicts_srp(rc):
        """Check for SRP conflicts"""
        all_tiles = rc.sense_nearby_map_infos()
        for surrounding_tile in all_tiles:
            if surrounding_tile.get_mark().is_ally():
                south = surrounding_tile.get_map_location().add(Direction.SOUTH)
                southwest = south.add(Direction.WEST)
                if rc.can_sense_location(south):
                    if not rc.sense_map_info(south).has_ruin():
                        if rc.can_sense_location(southwest):
                            if not rc.sense_map_info(southwest).has_ruin():
                                return True
                        else:
                            return True
                else:
                    return True
        return False
