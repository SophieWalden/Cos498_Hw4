# AI Class
# by zax

# This is the main file you will edit. The run_ai function's job
# is to issue two types of commands (see command.py):
# - BuildUnitCommand: asks the game engine to build a specific type
#     of unit at a specific city if the faction has enough cash
#     available.
# - MoveUnitCommand: asks the game engine to move a specific unit
#     in a specific direction. The engine will only move a unit
#     if the destination cell is free. If it is occupied by a friendly
#     unit, nothing happens. If it is occupied by another faction,
#     combat ensues.

import math
from collections import deque
from command import *
import random
import unit
from city import City
import time
import cell_terrain
import params

def create_flow_field(pos, gmap):
    flow_field = {}

    tile_costs = [[99999] * gmap.width for _ in range(gmap.height)]
    for v, c in gmap.cell_render_queue:
        if c.terrain == cell_terrain.Terrain.Water:
            tile_costs[v.y][v.x] = math.inf

    queue = deque([pos])
    tile_costs[pos[1]][pos[0]] = 0

    directions = [[-1, 0], [1, 0], [0, 1], [0, -1]]
    while queue:
        x, y = queue.popleft()

        for dx, dy in directions:
            new_x, new_y = x + dx, y + dy

            if 0 <= new_x < gmap.width and 0 <= new_y < gmap.height and tile_costs[new_y][new_x] != math.inf:
                new_cost = tile_costs[y][x] + 1

                if new_cost < tile_costs[new_y][new_x]:
                    tile_costs[new_y][new_x] = new_cost
                    queue.append((new_x, new_y))
    
    for j in range(gmap.height):
        for i in range(gmap.width):
            min_cost = math.inf
            best_dir = "S"

            for index, (dx, dy) in enumerate(directions):
                new_x, new_y = i + dx, j + dy

                if 0 <= new_x < gmap.width and 0 <= new_y < gmap.height:
                    if tile_costs[new_y][new_x] < min_cost:
                        min_cost = tile_costs[new_y][new_x]
                        best_dir = ["W","E","S","N"][index]

            flow_field[(i, j)] = best_dir

    return flow_field

class AI:
    # init:
    # Currently, the initializer adds nothing to the object.
    # You are welcome to modify to have a place to keep
    # information that persists across calls to run_ai().
    #
    # NOTE: AI objects are passed into the Faction initializer
    # when a faction is created (see the gen_factions() function
    # in the main.py file). If you'd like to subclass the AI class
    # to differentiate between faction behaviors, you are welcome
    # to do so.
    def __init__(self):
        self.cache_hit, self.cache_miss = 0, 0
        self.system = System()


    # run_ai
    # Parameters:
    # - faction_id: this is the faction_id of this AI object.
    #     Use it to access infomation in the other parameters.
    # - factions: dictionary of factions by faction_id.
    # - cities: dictionary of cities stored by faction_id.
    #     For example: cities[faction_id] would return all the
    #     the city objects owned by this faction.
    # - units: dictionary of all units by faction_id.
    #     Similar to the cities dictionary, units[faction_id]
    #     would return all unit objects belonging to the faction.
    # - gmap: the game map object. You can use this (if you wish)
    #     to get information about the map and terrain.
    #
    # Return:
    # This function should return a list of commands to be processed
    # by the game engine this turn.
    #
    # NOTE: You should replace the following code with your
    # own. The code currently gives the factions totally random
    # behavior. Totally random behavior, while interesting,
    # is not an acceptable solution.
    #
    # NOTE 2: Every ai has access to ALL game objects. This means
    # you can (and should) access the unit and city locations
    # of the other faction. I STRONGLY advise against manually
    # changing unit or city locations from the AI file. Doing so
    # circumvents checks made by the game engine and is likely to
    # have bad side effects. If you want something more actions
    # than those provided by the two commands, I suggest taking
    # the time to create additional Command subclasses and properly
    # implement them in the engine (main.py).

    def preturn_information(self, units, cities, faction_id, factions):
        current_faction = None
        current_units = units[faction_id]
        current_cities = cities[faction_id]
        current_cities_pos = set([(city.pos.x, city.pos.y) for city in current_cities])
        
        total_cities = sum(len(cities) for _, cities in cities.items())
        for name, faction in factions.items():
            if faction.ID == faction_id:
                current_faction = faction

        current_structures_pos = set([(struct.pos.x, struct.pos.y) for struct in current_faction.structures])
        current_units_pos = set([])
        for fid, units in units.items():
            for unit in units: current_units_pos.add((unit.pos.x, unit.pos.y))

        return current_faction, current_units, current_cities, current_cities_pos, current_units_pos, total_cities, current_structures_pos

    def update_faction_officers(self, current_faction, current_units):
        if current_faction.commander and current_faction.commander.dead: 
            current_faction.commander = None

        for unit in current_units:
            if unit.general_following and unit.general_following.dead == True:
                unit.general_following = None

        current_faction.generals = list(filter(lambda general: general.dead == False, current_faction.generals))

        if not current_faction.commander:
            current_faction.choose_commander(current_units)

        if current_faction.commander and current_faction.age % 25 == 0:
            current_faction.goal = current_faction.commander.choose_goal()

        retVal = True
        while retVal and len(current_faction.generals) < (len(current_units) // 5) + 1:
            retVal = current_faction.choose_general(current_units)
            
        for u in current_units:
            if u.rank == "soldier" and not u.general_following:
                u.choose_general(current_faction.generals)

    def unit_pathfinding(self, current_units, current_cities_pos, cities, move_cache, gmap, faction_id, current_faction):
        unit_commands = {}
        for u in current_units:
            if u.general_following:
                pos = (u.pos.x, u.pos.y)
                if pos == u.general_following.targeted_pos:
                    u.general_following.targeted_pos = None

                if pos in u.general_following.flow_field:
                    unit_commands[u.ID] = MoveUnitCommand(faction_id, u.ID, u.general_following.flow_field[pos])
  
            elif u.rank == "commander" and current_cities_pos: # Commander by default goes to closest city defensively
                u.targeted_pos = min(current_cities_pos, key=lambda pos: (pos[0] - u.pos.x)**2+(pos[1] - u.pos.y)**2)

            if u.ID not in unit_commands:
                rand_dir = random.choice(list(vec2.MOVES.keys()))
                unit_commands[u.ID] = MoveUnitCommand(faction_id, u.ID, rand_dir)

        return unit_commands

    def run_ai(self, faction_id, factions, cities, units, gmap, move_cache):
        current_faction, current_units, current_cities, current_cities_pos, current_units_pos, total_cities, current_structures_pos = self.preturn_information(units, cities, faction_id, factions)

        # Upkeep of management system
        self.update_faction_officers(current_faction, current_units)

        # AI System makes its decisions here
        self.system.build_units_queue = []
        self.build_structures_queue = []
        self.system.tick(current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache)

        # Constructing and returning all of the commands
        cmds = []
        for (city_id, utype) in self.system.build_units_queue:
            cmds.append(BuildUnitCommand(faction_id, city_id, utype))

        for (pos, building_type) in self.system.build_structures_queue:
            cmds.append(BuildStructureCommand(faction_id, current_faction, pos, building_type))
        
        for uid, cmd in self.unit_pathfinding(current_units, current_cities_pos, cities, move_cache, gmap, faction_id, current_faction).items():
            cmds.append(cmd)

        for u in current_units:
            if u.defecting:
                cmds.append(DefectCommand(faction_id, current_faction, u))
                u.defecting = False

        return cmds, move_cache


class System:
    def __init__(self):
        self.build_units_queue = []
        self.build_structures_queue = []

    def tick(self, current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache):
        for general in current_faction.generals:
            if current_faction.commander and current_faction.commander.soldiers_killed >= general.general_accepted_death_threshhold:
                general.defecting = True
            
            if general.targeting_age + 40 < current_faction.age:
                general.targeted_pos = None

            if general.targeted_pos and general.targeted_pos in current_structures_pos:
                general.targeted_pos = None

        

            
        can_buy = True
        if current_faction.goal[0] == "gather":
            if current_faction.goal[1] == "wood" and current_faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]):
                can_buy = True
            elif current_faction.goal[1] == "stone" and current_faction.can_build_structure(params.STRUCTURE_COST["miner"]):
                can_buy = True

            if can_buy:
                for general in current_faction.generals:
                    wanted_terrain = (cell_terrain.Terrain.Forest, cell_terrain.Terrain.Woodcutter) if current_faction.goal[1] == "wood" else (cell_terrain.Terrain.Stone, cell_terrain.Terrain.Miner)
                    if not general.targeted_pos or gmap.cells[vec2.Vec2(general.targeted_pos[0], general.targeted_pos[1])].terrain not in wanted_terrain:
                        terrain_found = general.choose_target_terrain(gmap, wanted_terrain, move_cache)
                        general.targeting_age = current_faction.age
        
                        if not terrain_found:
                            current_faction.goal = ["conquer", "closest"]

                            current_faction.reset_generals()
                            break

        if current_faction.goal[0] == "conquer" or not can_buy:
            for general in current_faction.generals:
                if (not general.targeted_pos or general.targeted_pos in current_cities_pos) and total_cities != len(current_cities):
                    general.choose_targeted_city(cities, factions, current_faction.goal[1], gmap, move_cache)
                    general.targeting_age = current_faction.age

                if total_cities == len(current_cities):
                    general.choose_targeted_unit(units, gmap, move_cache) 
                    general.targeting_age = current_faction.age
                
        city_indexes = list(range(len(current_cities)))

        if current_faction.goal[0] in ["conquer", "defend"]:
            for ci in city_indexes:
                self.build_units_queue.append((current_cities[ci].ID, random.choice(['R', 'S', 'P'])))

        for u in current_units:
            if gmap.cells[u.pos].terrain == cell_terrain.Terrain.Forest and current_faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]):
                self.build_structures_queue.append(((u.pos.x, u.pos.y), "woodcutter"))

            if gmap.cells[u.pos].terrain == cell_terrain.Terrain.Stone and current_faction.can_build_structure(params.STRUCTURE_COST["miner"]):
                self.build_structures_queue.append(((u.pos.x, u.pos.y), "miner"))
