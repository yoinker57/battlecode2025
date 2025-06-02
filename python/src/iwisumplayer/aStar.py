from battlecode25.stubs import *

directions = [
    Direction.NORTH,
    Direction.NORTHEAST,
    Direction.EAST,
    Direction.SOUTHEAST,
    Direction.SOUTH,
    Direction.SOUTHWEST,
    Direction.WEST,
    Direction.NORTHWEST,
]

def max(a, b):
    return a if a > b else b

def heuristic(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))  # Chebyshev distance

def greedy_best_first(start, goal, walls_set, occupied_set):
    current = start
    path = []

    while current != goal:
        best_neighbor = None
        best_h = 99999

        for d in directions:
            neighbor = current.add(d)

            if (not on_the_map(neighbor) or 
                neighbor in walls_set or 
                neighbor in occupied_set):
                continue

            h = heuristic(neighbor, goal)
            if h < best_h:
                best_h = h
                best_neighbor = neighbor

        if best_neighbor is None:
            break  # utknął

        path.append(best_neighbor)
        current = best_neighbor

    return path
