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
import neuralNetworks
import numpy as np

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
    def __init__(self, fid, color, starting_model=None):
        self.cache_hit, self.cache_miss = 0, 0

        # Color based assignment so we can know which color is being controlled how    

        if params.MODE == "nature":
           
            if color == (200, 0, 0):
                self.system = GANNSystem()
            else:
                self.system = AggressorSystem()
          
        else:
            
            if starting_model:
                self.system = GANNSystem(starting_model)
            elif color == (200, 0, 0):
                self.system = GANNSystem("./models/model_23.npz")
            else:
                self.system = AggressorSystem()
        

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

        if not current_faction.commander and self.system.need_commander:
            current_faction.choose_commander(current_units)

        if current_faction.commander and current_faction.age % 25 == 0:
            current_faction.goal = current_faction.commander.choose_goal()

        retVal = True
        while retVal and len(current_faction.generals) < (len(current_units) // 300) + 1:
            retVal = current_faction.choose_general(current_units)
            
        for u in current_units:
            if u.rank in ["soldier", "commander"] and not u.general_following:
                u.choose_general(current_faction.generals)

    def unit_pathfinding(self, current_units, current_cities_pos, cities, move_cache, gmap, faction_id, current_faction, current_structures_pos):
        unit_commands = {}
        for u in current_units:
            pos = (u.pos.x, u.pos.y)
            if u.general_following:
                if pos == u.general_following.targeted_pos:
                    u.general_following.targeted_pos = None

                if pos in u.general_following.flow_field:
                    unit_commands[u.ID] = MoveUnitCommand(faction_id, u.ID, u.general_following.flow_field[pos])

            if u.flow_field:
                unit_commands[u.ID] = MoveUnitCommand(faction_id, u.ID, u.flow_field[pos])

            elif u.rank == "commander" and current_cities_pos: # Commander by default goes to closest city defensively
                u.targeted_pos = min(current_cities_pos, key=lambda pos: (pos[0] - u.pos.x)**2+(pos[1] - u.pos.y)**2)
                

            if u.targeted_pos and u.targeted_pos in current_cities_pos or u.targeted_pos in current_structures_pos:
                u.targeted_pos = None

        return unit_commands

    def run_ai(self, faction_id, factions, cities, units, gmap, move_cache, defecting_enabled, unit_dict, top_models):
        current_faction, current_units, current_cities, current_cities_pos, current_units_pos, total_cities, current_structures_pos = self.preturn_information(units, cities, faction_id, factions)

        # Upkeep of management system
        self.update_faction_officers(current_faction, current_units)

        # AI System makes its decisions here
        self.system.build_units_queue = []
        self.build_structures_queue = []
        self.system.tick(current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache, top_models, unit_dict)

        # Constructing and returning all of the commands
        cmds = []
        for (city_id, utype, upgrades) in self.system.build_units_queue:
            cmds.append(BuildUnitCommand(faction_id, city_id, utype, upgrades))

        for (pos, building_type) in self.system.build_structures_queue:
            cmds.append(BuildStructureCommand(faction_id, current_faction, pos, building_type))
        
        for uid, cmd in self.unit_pathfinding(current_units, current_cities_pos, cities, move_cache, gmap, faction_id, current_faction, current_structures_pos).items():
            cmds.append(cmd)

        for u in current_units:
            if defecting_enabled and u.defecting:
                cmds.append(DefectCommand(faction_id, current_faction, u))
                u.defecting = False

        return cmds, move_cache


class AggressorSystem:
    def __init__(self):
        """It doesn't care what its soldiers, generals, or even the commander thinks, all the aggressor wants is to send units towards enemy cities"""
        self.build_units_queue = []
        self.build_structures_queue = []
        self.need_commander = True

    def tick(self, current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache, top_models, unit_dict):        
        for general in current_faction.generals:
            if not general.targeted_pos and total_cities != len(current_cities):
                targeted_point = general.choose_targeted_city(cities, factions, current_faction.goal[1], gmap, move_cache)
                general.targeted_pos = targeted_point
                general.create_flow_field(targeted_point, gmap, move_cache)

                general.targeting_age = current_faction.age

            if total_cities == len(current_cities):
                general.choose_targeted_unit(units, gmap, move_cache) 
                general.targeting_age = current_faction.age

        for ci in list(range(len(current_cities))):
            self.build_units_queue.append((current_cities[ci].ID, random.choice(['R', 'S', 'P']), {"wood": current_faction.materials["wood"]//4, "stone": current_faction.materials['stone']//4}))




class BalancedSystem:
    def __init__(self):
        """Base system showing off both the capability to take cities and gather materials, but doesn't have any great strategy"""
        self.build_units_queue = []
        self.build_structures_queue = []
        self.need_commander = True

    def tick(self, current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache, top_models, unit_dict):
        for general in current_faction.generals:
            if current_faction.commander and current_faction.commander.soldiers_killed >= general.general_accepted_death_threshhold:
                general.defecting = True
            
            if general.targeting_age + 40 < current_faction.age:
                general.targeted_pos = None


        can_buy = False
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
                    targeted_point = general.choose_targeted_city(cities, factions, current_faction.goal[1], gmap, move_cache)
                    general.targeted_pos = targeted_point
                    general.create_flow_field(targeted_point, gmap, move_cache)
                    general.targeting_age = current_faction.age

                if total_cities == len(current_cities):
                    general.choose_targeted_unit(units, gmap, move_cache) 
                    general.targeting_age = current_faction.age
                
        city_indexes = list(range(len(current_cities)))

        if current_faction.goal[0] != "gather" or random.random() > 0.8:
            for ci in city_indexes:
                self.build_units_queue.append((current_cities[ci].ID, random.choice(['R', 'S', 'P']), {"wood": current_faction.materials["wood"]//10, "stone": current_faction.materials['stone']//10}))

        for u in current_units:
            if gmap.cells[u.pos].terrain == cell_terrain.Terrain.Forest and current_faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]):
                self.build_structures_queue.append(((u.pos.x, u.pos.y), "woodcutter"))

            if gmap.cells[u.pos].terrain == cell_terrain.Terrain.Stone and current_faction.can_build_structure(params.STRUCTURE_COST["miner"]):
                self.build_structures_queue.append(((u.pos.x, u.pos.y), "miner"))


class DefenceSystem:
    def __init__(self):
        """Showcases a turtling effect to maintain cities, NOT BUILT OUT YET"""
        self.build_units_queue = []
        self.build_structures_queue = []
        self.need_commander = True

    def tick(self, current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache, top_models):
   
        def dist(x1, y1, x2, y2):
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** .5

        city_strength = {}
        for ci in range(len(current_cities)):
            city = current_cities[ci] 
            city_strength[ci] = sum(dist(city.pos.x, city.pos.y, unit.pos.x, unit.pos.y) < 4 for unit in current_units)

        cities_sorted = sorted(city_strength.keys(), key=lambda x: city_strength[x])

        cost = unit.UNIT_COSTS["R"]
        while cities_sorted and current_faction.materials["gold"] >= cost:
            ci = cities_sorted.pop(0)
            self.build_units_queue.append((current_cities[ci].ID, random.choice(['R', 'S', 'P']), {"wood": 0, "stone": 0}))



def create_new_model(models):
    parent1 = random.choice(models)
    parent2 = random.choice(models)

    return parent1.crossover(parent2)


class Stats:
    def __init__(self, unit, age):
        self.kills = unit.soldiers_killed
        self.losses = unit.soldiers_lost
        self.cities = unit.cities_gained
        self.cities_lost = unit.cities_lost
        self.age = age

class GANNSystem:
    def __init__(self, base_models=None):
        """Uses the Neural Networks as ways for generals to decide to retreat, attack, or go for resources"""
        self.build_units_queue = []
        self.build_structures_queue = []
        self.base_model = base_models
        self.need_commander = False

    def score_model(self, general, top_models, faction):
        score = 0

        
            

        score += general.soldiers_killed * 200
        score -= general.soldiers_lost * 250

        score += general.cities_gained * 500
        score -= general.cities_lost * 510
        
        score -= (faction.age - general.creation_age) * 20



        
        for i, (old_score, model, _) in enumerate(top_models):
            if model == general.NNModel:
                if score > old_score:
                    top_models[i][0] = score
                    top_models[i][2] = Stats(general, faction.age - general.creation_age) 
                    top_models.sort(key=lambda x: x[0], reverse=True)

                break
        
        else:
            if len(top_models) < 4:
                top_models.append([score, general.NNModel,Stats(general, faction.age - general.creation_age) ])
                top_models.sort(key=lambda x: x[0], reverse=True)
            elif score > top_models[-1][0]:
                top_models.append([score, general.NNModel, Stats(general, faction.age - general.creation_age) ])
                top_models.sort(key=lambda x: x[0], reverse=True)
                top_models.pop(-1)

    def make_decision(self, general, current_cities, total_cities, current_cities_pos, cities, factions, current_faction, unit_dict, gmap, move_cache):

        def dist(x1, y1, x2, y2):
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** .5
        
        def enemys_around_this_point(point, dist):
            nearby_enemy_units = 0
            for j in range(-dist, dist+1):
                for i in range(-dist, dist+1):
                    new_pos = vec2.Vec2(i + general.pos.x, j + general.pos.y)
                    if new_pos not in unit_dict.by_pos: continue

                    found_unit = unit_dict.by_pos[new_pos]
                    if found_unit and found_unit.faction_id != general.faction_id:
                        nearby_enemy_units += 1

            nearby_enemy_units = nearby_enemy_units / (((dist * 2) + 1) ** 2)
            return nearby_enemy_units

        max_map_distance = dist(0, 0, gmap.width, gmap.height)
        # Make decision using NN Model
        inputs = []

        troop_health = sum(unit.health for unit in general.soldiers_commanding) + general.health
        troop_max_health = sum(unit.maxhealth for unit in general.soldiers_commanding) + general.maxhealth
        troop_percentage_health = troop_health / troop_max_health
        inputs.append(troop_percentage_health)

        troop_size = len(general.soldiers_commanding) / 200
        inputs.append(troop_size)

        cities_owned_percentage = len(current_cities) / total_cities
        inputs.append(cities_owned_percentage)

        if len(current_cities) == 0: distance_to_nearest_ally_city = 0
        else: distance_to_nearest_ally_city = min(dist(city[0], city[1], general.pos.x, general.pos.y) for city in current_cities_pos)
        distance_to_nearest_ally_city_normalized = distance_to_nearest_ally_city / max_map_distance
        inputs.append(distance_to_nearest_ally_city_normalized)

        if len(current_cities) == total_cities: distance_to_nearest_enemy_city = 0
        else: distance_to_nearest_enemy_city = min(min(dist(city.pos.x, city.pos.y, general.pos.x, general.pos.y) for city in cities[fid]) for fid in factions if fid != current_faction.ID and cities[fid])
        distance_to_nearest_enemy_city = distance_to_nearest_enemy_city / max_map_distance
        inputs.append(distance_to_nearest_enemy_city)

        # Get the amount of enemies at each of the destination points
        possible_points = [(general.pos.x, general.pos.y),
                            (-99,-99) if not current_cities_pos else min(current_cities_pos, key = lambda pos: dist(pos[0], pos[1], general.pos.x, general.pos.y)),
                           general.choose_targeted_city(cities, factions, "closest", gmap, move_cache),
                           general.choose_targeted_city(cities, factions, "furthest", gmap, move_cache)]
        for point in possible_points:
            if point: inputs.append(enemys_around_this_point(point, 4))
            else: inputs.append(0)


        # can_buy_structure = int(current_faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]) and current_faction.can_build_structure(params.STRUCTURE_COST["miner"]))
        # inputs.append(can_buy_structure)
        
        # Feed inputs to decision model
        decision = general.NNModel.feedForward(inputs)

        # Move based on decision
        decision = np.argmax(decision)

        return decision

    def tick(self, current_faction, current_units, current_cities, current_cities_pos, current_units_pos, factions, units, gmap, cities, total_cities, current_structures_pos, move_cache, top_models, unit_dict):
        def dist(x1, y1, x2, y2):
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** .5
        
        for general in current_faction.generals:
            if general.NNModel == None:
                if self.base_model:
                    new_model = neuralNetworks.Model()
                    new_model.load(self.base_model)
                elif len(top_models) > 0:
                    new_model = create_new_model([model[1] for model in top_models])
                    new_model.mutate()
                else:
                    new_model = neuralNetworks.Model()

                general.NNModel = new_model
            
            if total_cities == len(current_cities):
                 general.choose_targeted_unit(units, gmap, move_cache) 

            else:

                decision = self.make_decision(general, current_cities, total_cities, current_cities_pos, cities, factions, current_faction, unit_dict, gmap, move_cache)
                
                
                if decision == 0 and current_cities_pos: # Move to nearest ally city
                    general.targeted_pos = min(current_cities_pos, key = lambda pos: dist(pos[0], pos[1], general.pos.x, general.pos.y))
                    if general.targeted_pos:
                        general.create_flow_field(general.targeted_pos, gmap, move_cache)

                if decision == 1: #Move towards nearest enemy city:
                    general.targeted_pos = general.choose_targeted_city(cities, factions, "closest", gmap, move_cache)
                    if general.targeted_pos:
                        general.create_flow_field(general.targeted_pos, gmap, move_cache)

                if decision == 2: #Move towards furthest enemy city:
                    general.targeted_pos = general.choose_targeted_city(cities, factions, "furthest", gmap, move_cache)
                    
                    if general.targeted_pos:
                        general.create_flow_field(general.targeted_pos, gmap, move_cache)

                # if decision == 2: # Move towards nearest resource
                #     general.choose_target_terrain(gmap, (cell_terrain.Terrain.Forest, cell_terrain.Terrain.Stone), move_cache)

                if decision == 3: # Defend current position this turn
                    pass
        
                general.NNModel.chosen_percentage[decision] += 1
                general.NNModel.chosen_count += 1

                # self.score_model(general, top_models, current_faction)



        for ci in list(range(len(current_cities))):
            self.build_units_queue.append((current_cities[ci].ID, random.choice(['R', 'S', 'P']), {"wood": current_faction.materials["wood"]//10, "stone": current_faction.materials['stone']//10}))
