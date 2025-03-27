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
        pass


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
    
    def run_ai(self, faction_id, factions, cities, units, gmap):

        # A list to hold our commands. This gets returned by
        # the function.

        start_time = time.perf_counter()
        time_chunks = {}
        cmds = []

        current_faction = None
        current_units = units[faction_id]
        current_cities = cities[faction_id]
        current_cities_pos = set([(city.pos.x, city.pos.y) for city in current_cities])
        for name, faction in factions.items():
            if faction.ID == faction_id:
                current_faction = faction

        current_units_pos = set([])
        for fid, units in units.items():
            for unit in units: current_units_pos.add((unit.pos.x, unit.pos.y))

        time_chunks["get_units"] = time.perf_counter() - start_time

        # Checking for dead commander / generals
        if current_faction.commander and current_faction.commander.dead: 
            current_faction.commander = None

        for general in current_faction.generals:
            for unit in current_units:
                if unit.general_following and unit.general_following.dead == True:
                    unit.general_following = False

        current_faction.generals = list(filter(lambda general: general.dead == False, current_faction.generals))
        

        if not current_faction.commander:
            current_faction.choose_commander(current_units)

        retVal = True
        while retVal and len(current_faction.generals) < len(current_units) // 5:
            retVal = current_faction.choose_general(current_units)

        time_chunks["assign_general_commander"] = time.perf_counter() - time_chunks["get_units"] - start_time
        

        if current_faction.goal[0] == "conquer":
            for general in current_faction.generals:
                if not general.targeted_city:
                    general.choose_targeted_city(cities)
                
                elif (general.targeted_city.pos.x, general.targeted_city.pos.y) in current_cities_pos:
                    general.choose_targeted_city(cities)

        if current_faction.goal[0] == "gather":
            for general in current_faction.generals:
                if not general.targeted_city or gmap.cells[general.targeted_city].terrain != cell_terrain.Terrain.Forest:
                    terrain_found = general.choose_target_terrain(gmap, cell_terrain.Terrain.Forest)

                    if not terrain_found:
                        current_faction.goal = ["conquer"]

                        current_faction.reset_generals()
                        break
                

        # Overview: randomly select a city we own and randomly
        # select a unit type (utype). Create a BuildUnitCommand
        # This is done every turn knowing most will fail because
        # the faction does not have enough money to build them.


        for faction in factions.values():
            fid = faction.ID
            my_cities = cities[fid]
            city_indexes = list(range(len(my_cities)))
            random.shuffle(city_indexes)
            for ci in city_indexes:
                cmd = BuildUnitCommand(faction_id,
                                my_cities[ci].ID, 
                                random.choice(['R', 'S', 'P']))
                cmds.append(cmd)

        # # Overview: issue a move to every unit giving a random
        # # direction. Directions can be found in the vec2.py file.
        # # They are single char strings: 'N', 'E', 'W', 'S'.
        # my_units = units[faction_id]

        time_chunks["targeted_city_build"] = time.perf_counter() - time_chunks["assign_general_commander"]     - start_time    
        

        for u in current_units:

            if u.rank == "soldier" and not u.general_following:
                u.choose_general(current_faction.generals)

            targeted_city = None
            pos = (u.pos.x, u.pos.y)
            if not u.general_following and pos in current_cities_pos:
    
                rand_dir = random.choice(list(vec2.MOVES.keys()))
                cmd = MoveUnitCommand(faction_id, u.ID, rand_dir)
                cmds.append(cmd)

            elif u.general_following:
                targeted_city = u.general_following.targeted_city
            elif u.targeted_city:
                targeted_city = u.targeted_city
            elif u.rank == "commander" and current_cities_pos:
                targeted_city_pos = min(current_cities_pos, key=lambda pos: (pos[0] - u.pos.x)**2+(pos[1] - u.pos.y)**2)
                targeted_city = City("_", vec2.Vec2(targeted_city_pos[0], targeted_city_pos[1]), "_", "_")
            elif len(current_cities_pos) == 0:
                u.choose_targeted_city(cities)
                targeted_city = u.targeted_city
            

            if targeted_city:
                try:
                    targeted_pos = targeted_city.pos
                except Exception:
                    targeted_pos = targeted_city

                available_moves = []
                for name, direction in vec2.MOVES.items():
                    new_pos = (u.pos.x + direction.x, u.pos.y + direction.y)
                    if new_pos not in current_units_pos:
                        available_moves.append((name, direction))

                if available_moves:
                    targeted_move = min(available_moves, key=lambda move: ((u.pos.x+move[1].x)-targeted_pos.x)**2+((u.pos.y+move[1].y)-targeted_pos.y)**2 + random.uniform(-1, 1))[0]
                    cmd = MoveUnitCommand(faction_id, u.ID, targeted_move)
                    cmds.append(cmd)

            if current_faction.goal[0] == "gather" and gmap.cells[u.pos].terrain == cell_terrain.Terrain.Forest:
                cmds.append(BuildStructureCommand(faction_id, (u.pos.x, u.pos.y), "woodcutter"))
                

        time_chunks["units_moved"] = time.perf_counter() - time_chunks["targeted_city_build"]        - start_time

        # print("\n"*2, "-"*40)
        # for key, val in time_chunks.items():
        #     print(f"{key}: {val:f}")

        # return all the command objects.
        return cmds
