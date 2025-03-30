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

from command import *
import random
import unit
from city import City
import time
import cell_terrain
import params

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

        current_units_pos = set([])
        for fid, units in units.items():
            for unit in units: current_units_pos.add((unit.pos.x, unit.pos.y))

        return current_faction, current_units, current_cities, current_cities_pos, current_units_pos, total_cities

    def update_faction_officers(self, current_faction, current_units):
        if current_faction.commander and current_faction.commander.dead: 
            current_faction.commander = None

        for unit in current_units:
            if unit.general_following and unit.general_following.dead == True:
                unit.general_following = False

        current_faction.generals = list(filter(lambda general: general.dead == False, current_faction.generals))

        if not current_faction.commander:
            current_faction.choose_commander(current_units)

        retVal = True
        while retVal and len(current_faction.generals) < len(current_units) // 5:
            retVal = current_faction.choose_general(current_units)
            
        for u in current_units:
            if u.rank == "soldier" and not u.general_following:
                u.choose_general(current_faction.generals)

    def pathplan(self, u, move_cache, gmap):
        """Given a unit, this func performs A* to make a move_queue to get it its targeted point"""

        if u.targeted_pos:
            cache_key = (u.pos.x, u.pos.y, u.targeted_pos[0], u.targeted_pos[1])
            if cache_key in move_cache and random.random() < 0.9: 
                self.cache_hit += 1
                u.move_queue = move_cache[cache_key].copy()
            else:
                self.cache_miss += 1
                seen_nodes = set([(u.pos.x, u.pos.y)])
                queue = [[u.pos.x, u.pos.y, {"end_pos": u.targeted_pos}]]
        
                while queue:
                    x, y, path = queue.pop(queue.index(min(queue, key=lambda pos: random.random() * 10 + abs(pos[0] - u.pos.x) + abs(pos[1] - u.pos.y) + abs(pos[0] - u.targeted_pos[0]) + abs(pos[1] - u.targeted_pos[1]))))

                    potential_cache_key = (x, y, u.targeted_pos[0], u.targeted_pos[1])
                    if potential_cache_key in u.move_queue:
                        additional_moves = u.move_queue[potential_cache_key]
                        for key, val in additional_moves.items():
                            path[key] = val
                        u.move_queue = path
                        break
                
                    if x == u.targeted_pos[0] and y == u.targeted_pos[1]:
                        u.move_queue = path
                        break

                    for name, direction in vec2.MOVES.items():
                        new_x, new_y = x + direction.x, y + direction.y
                        new_x %= gmap.width
                        new_y %= gmap.height

                        if (new_x, new_y) not in seen_nodes and gmap.cells[vec2.Vec2(new_x, new_y)].terrain != cell_terrain.Terrain.Water:
                            seen_nodes.add((new_x, new_y))
                            
                            new_path = path.copy()
                            new_path[(x, y)] = name
                            queue.append([new_x, new_y, new_path])
                        
                move_cache[cache_key] = u.move_queue.copy()
                
                # To speed up computation every point thats pathing to the same point on the path can follow the same path
                pos = [u.pos.x, u.pos.y]
                while pos[0] != u.targeted_pos[0] and pos[1] != u.targeted_pos[1]:
                    if (pos[0], pos[1]) not in u.move_queue: break
                    next_move = u.move_queue[(pos[0], pos[1])]
                    move = {"W": [-1, 0], "E": [1, 0], "N": [0, -1], "S": [0, 1]}[next_move]
                    new_x, new_y = pos[0] + move[0], pos[1] + move[1]
                    new_x %= gmap.width
                    new_y %= gmap.height

                    pos = [new_x, new_y]

                    new_cache_key = (new_x, new_y, u.targeted_pos[0], u.targeted_pos[1]) 
                    move_cache[new_cache_key] = u.move_queue.copy()

    def unit_pathfinding(self, current_units, current_cities_pos, cities, move_cache, gmap, faction_id):
        unit_commands = {}
        for u in current_units:
            if u.general_following:
                if u.general_following.dead:
                    u.move_queue = {}
                
                elif u.general_following.targeted_pos and u.move_queue and (u.general_following.targeted_pos[0] != u.move_queue["end_pos"][0] or u.general_following.targeted_pos[1] != u.move_queue["end_pos"][1]):
                    u.move_queue = {}

            if u.general_following:
                u.targeted_pos = u.general_following.targeted_pos
            elif u.rank == "commander" and current_cities_pos: # Commander by default goes to closest city defensively
                u.targeted_pos = min(current_cities_pos, key=lambda pos: (pos[0] - u.pos.x)**2+(pos[1] - u.pos.y)**2)
            elif len(current_cities_pos) == 0:
                u.choose_targeted_city(cities)

            pos = (u.pos.x, u.pos.y)
            if not u.move_queue or pos not in u.move_queue or pos == u.move_queue["end_pos"] and random.random() < 0.5:
                self.pathplan(u, move_cache, gmap)

            if pos in u.move_queue:
                unit_commands[u.ID] = MoveUnitCommand(faction_id, u.ID, u.move_queue[pos])

            if u.ID not in unit_commands:
                rand_dir = random.choice(list(vec2.MOVES.keys()))
                unit_commands[u.ID] = MoveUnitCommand(faction_id, u.ID, rand_dir)

        return unit_commands

    def run_ai(self, faction_id, factions, cities, units, gmap, move_cache):
        current_faction, current_units, current_cities, current_cities_pos, current_units_pos, total_cities = self.preturn_information(units, cities, faction_id, factions)

        # Upkeep of management system
        self.update_faction_officers(current_faction, current_units)

        # AI System makes its decisions here
        self.system.build_units_queue = []
        self.build_structures_queue = []
        self.system.tick(current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities)

        # Constructing and returning all of the commands
        cmds = []
        for (city_id, utype) in self.system.build_units_queue:
            cmds.append(BuildUnitCommand(faction_id, city_id, utype))

        for (pos, building_type) in self.system.build_structures_queue:
            cmds.append(BuildStructureCommand(faction_id, current_faction, pos, building_type))
        
        for uid, cmd in self.unit_pathfinding(current_units, current_cities_pos, cities, move_cache, gmap, faction_id).items():
            cmds.append(cmd)

        return cmds, move_cache


class System:
    def __init__(self):
        self.build_units_queue = []
        self.build_structures_queue = []

    def tick(self, current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities):
        if current_faction.goal[0] == "conquer":
            for general in current_faction.generals:
                if not general.targeted_pos:
                    general.choose_targeted_city(cities)
                
                elif general.targeted_pos in current_cities_pos:
                    general.choose_targeted_city(cities)

                if total_cities == len(current_cities):
                    general.choose_targeted_unit(units) 

                

        if current_faction.goal[0] == "gather":
            for general in current_faction.generals:
                if not general.targeted_pos or gmap.cells[vec2.Vec2(general.targeted_pos[0], general.targeted_pos[1])].terrain != cell_terrain.Terrain.Forest:
                    terrain_found = general.choose_target_terrain(gmap, cell_terrain.Terrain.Forest)

                    if not terrain_found:
                        current_faction.goal = ["conquer"]

                        current_faction.reset_generals()
                        break
            
        city_indexes = list(range(len(current_cities)))
        for ci in city_indexes:
            self.build_units_queue.append((current_cities[ci].ID, random.choice(['R', 'S', 'P'])))

        for u in current_units:
            if gmap.cells[u.pos].terrain == cell_terrain.Terrain.Forest and current_faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]):
                self.build_structures_queue.append(((u.pos.x, u.pos.y), "woodcutter"))

            if gmap.cells[u.pos].terrain == cell_terrain.Terrain.Stone and current_faction.can_build_structure(params.STRUCTURE_COST["miner"]):
                self.build_structures_queue.append(((u.pos.x, u.pos.y), "miner"))