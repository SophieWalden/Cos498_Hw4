import random
import copy
import pygame
import pygame.freetype
import game_map
import params
import faction
import ai
import city
import vec2
import unit
import command
import os
import cell_terrain
import math
from cell import Cell
import sys
from collections import defaultdict
from faction import Faction
import cProfile, pstats
from collections import OrderedDict
from termcolor import colored
import isometricDisplay

# ###################################################################
# DISPLAY
# The display part of the engine. Unless you want to mess with
# the look and feel (add sprites or something) you probably don't need
# to mess with anything in this section
# ####################################################################

# ###############################################################
# GAME GENERATION FUCNTIONS
# This section generates the map, factions and cities.
# If you add things to the game (additional terrain, factions,
# city types, etc), you'll need to edit these functions to have
# them placed on the map
# ###############################################################
TILE_X_OFFSET = 24
TILE_Y_OFFSET = 12
IMAGE_SIZE = 50

def gen_game_map(width, height):
    return game_map.GameMap(width, height)

POSSIBLE_FACTIONS = [
    ["Red", (200, 0, 0)],
    ["Blue", (0, 0, 200)],
    ["Green", (0, 200, 0)],
    ["Yellow", (200, 200, 0)],
    ["Purple", (128, 0, 128)],
    ["Cyan", (0, 200, 200)],
    ["Magenta", (255, 0, 255)],
    ["Pink", (255, 105, 180)],
    ["Brown", (139, 69, 19)],
    ["Black", (0, 0, 0)],
    ["White", (255, 255, 255)],
    ["Gray", (169, 169, 169)],
    ["Violet", (148, 0, 211)], 
    ["Indigo", (75, 0, 130)],
    ["Turquoise", (48, 213, 200)], 
    ["Teal", (0, 128, 128)],
    ["Lime", (50, 205, 50)], 
    ["Orange", (255, 165, 0)],  
    ["Maroon", (128, 0, 0)],  
    ["Gold", (255, 215, 0)],  
    ["Deep Sky Blue", (0, 191, 255)],  
    ["Olive", (128, 128, 0)],  
    ["Navy", (0, 0, 128)],  
    ["Lavender", (230, 230, 250)],  
    ["Crimson", (220, 20, 60)],  
    ["Charcoal", (54, 69, 79)],  
    ["Periwinkle", (204, 204, 255)],  
    ["Amber", (255, 191, 0)],  
    ["Rose", (255, 0, 127)],  
    ["Mint", (189, 252, 201)],  
    ["Sapphire", (15, 82, 186)],  
    ["Emerald", (80, 200, 120)],  
    ["Ruby", (224, 17, 95)],  
    ["Azure", (0, 127, 255)],  
]

def get_faction_name(chosen_names):
    if len(chosen_names) == len(params.FACTION_NAMES):
        return random.choice(params.FACTION_NAMES)

    name = random.choice(params.FACTION_NAMES)
    while name in chosen_names:
        name = random.choice(params.FACTION_NAMES)

    return name

def gen_factions(gmap, model_eval):

    factions = {}
    chosen_names = []
    while len(factions) != params.FACTIONS_COUNT:
        name = get_faction_name(chosen_names)
        chosen_names.append(name)

        _, color = POSSIBLE_FACTIONS[len(factions)]
        factions[name] = faction.Faction(
            name, params.STARTING_FACTION_MONEY,
            ai.AI(name, color, model_eval if color == (200, 0, 0) else None), color, len(factions) * 999999999, name
        )
  
    return factions

def gen_cities(gmap, faction_ids):
    city_positions = []
    cities = []
    faction_id_index = 0
    
    for i in range(params.CITIES_PER_FACTION*len(faction_ids)):

        # A new red city
        new_city_pos = None
        while True:
            new_city_pos = vec2.Vec2(
                random.randrange(gmap.width),
                random.randrange(gmap.height))
            if new_city_pos not in city_positions and gmap.cells[new_city_pos].terrain != cell_terrain.Terrain.Water:
                city_positions.append(new_city_pos)
                break

        fid = faction_ids[faction_id_index]
        faction_id_index = (faction_id_index+1)%len(faction_ids)
            
        c = city.City(
            params.get_random_city_ID(),
            new_city_pos,
            fid, params.CITY_INCOME)


        cities.append(c)
        
    return cities

# ###########################################################
# GAME ENGINE CODE
# See specific function comments below
# ##########################################################

# FactionPreTurn:
# You don't need to edit this unless you make city resources
# more complex.
# - awards each faction its income from the cities
# - stores cities in the city dictionary passed onto the AI.
def FactionPreTurn(cities, faction):

    faction_cities = []

    # #####################################################
    # FACTION DATA
    
    # Award income
    for c in cities:
        if c.faction_id == faction.ID:
            income = c.generate_income()
            faction.materials['gold'] += income
            

    for structure in faction.structures:
        for key, val in structure.generate_material().items():
            faction.materials[key] += val

    faction.age += 1

    # #####################################################
    # CITY DATA
    for c in cities:
        if c.faction_id == faction.ID:
            faction_cities.append(c)

    return faction_cities
    
# Turn:
# The actual turn taking function. Calls each faction's ai
# Gathers all the commands in a giant list and returns it.
def Turn(factions, gmap, cities_by_faction, units_by_faction, move_cache, unit_dict, top_models):
    commands = []

    for fid, f in factions.items():
        cmds, move_cache = f.run_ai(factions, cities_by_faction, units_by_faction, gmap, move_cache, params.MODE != "versus", unit_dict, top_models) 
        commands.extend(cmds)

    return commands, move_cache

def shuffle(commands):
    """
    Random shuffling while more fair for multiple players made complex planning for AIs too messy
    as a solution this shuffle randomizes the order commands are in, but keeps every command in the same
    relative position for each faction
    """

    factions_commands = {}
    new_commands = []

    for command in commands:
        fid = command.faction_id

        if fid not in factions_commands: factions_commands[fid] = []
        factions_commands[fid].append(command)

    queued_commands = list(factions_commands.values())
    while queued_commands:
        random_index = random.randint(0, len(queued_commands) - 1)
        new_commands.append(queued_commands[random_index].pop(0))

        if len(queued_commands[random_index]) == 0: 
            queued_commands.pop(random_index)
    
    return new_commands


# RunAllCommands:
# Executes all commands from the current turn.
# Shuffles the commands to reduce P1 bias (maybe).
# Basically this is just a dispatch function.
def RunAllCommands(commands, factions, unit_dict, cities, gmap, structures):

    commands = shuffle(commands)
    combat_positions = []
    buidling_positions = []
    
    move_list = []
    for cmd in commands:
        if isinstance(cmd, command.MoveUnitCommand):
            combat_position = RunMoveCommand(cmd, factions, unit_dict, cities, gmap, move_list)
            if combat_position: combat_positions.append(combat_position)
        elif isinstance(cmd, command.BuildUnitCommand):
            RunBuildCommand(cmd, factions, unit_dict, cities, gmap)
        elif isinstance(cmd, command.BuildStructureCommand):
            building_pos = RunBuildStructureCommand(cmd, gmap, structures)
            if building_pos: buidling_positions.extend(building_pos)
        elif isinstance(cmd, command.DefectCommand):
            RunDefectCommand(cmd, factions, unit_dict)
        else:
            print(f"Bad command type: {type(cmd)}")

    return combat_positions, buidling_positions

def RunDefectCommand(cmd, factions, unit_dict):
    faction_id, current_faction, general = cmd.faction_id, cmd.faction, cmd.unit
    if general.dead or general.defected_times != 0: return

    name = get_faction_name(factions.keys())

    alive_colors = [faction.color for fid, faction in factions.items()]
    _, color = random.choice(POSSIBLE_FACTIONS)
    while color in alive_colors:
        _, color = random.choice(POSSIBLE_FACTIONS)

    factions[name] = Faction(
        name, params.STARTING_FACTION_MONEY,
        ai.AI(name, color), color, len(factions) * 999999999, name, general
    )
    new_unit_list = []
    units_to_remove_index = []
    for i, unit in enumerate(unit_dict.by_faction[faction_id]):
        if unit.ID == general.ID or unit.general_following and unit.general_following.ID == general.ID:
            units_to_remove_index.append(i)
            new_unit_list.append(unit)
            unit.faction_id = name
            unit.move_queue = {}
            unit.creation_age = 0

    general.creation_age = 0
    general.rank = "commander"
    if general in current_faction.generals: current_faction.generals.remove(general)
    for index in units_to_remove_index[::-1]:
        unit_dict.by_faction[faction_id].pop(index)
    general.defected_times += 1

    unit_dict.by_faction[name] = new_unit_list[:]


def RunBuildStructureCommand(cmd, gmap, structures):
    building_pos = []

    position = vec2.Vec2(cmd.pos[0], cmd.pos[1])
    succesful_build = False

    if cmd.utype == "woodcutter" and cmd.faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]) and gmap.cells[position].terrain == cell_terrain.Terrain.Forest:
        gmap.cells[position] = Cell(cell_terrain.Terrain.Woodcutter, position, cmd.faction)
        building_pos.append((position, cmd.utype))

        for key, val in params.STRUCTURE_COST["woodcutter"].items():
            cmd.faction.materials[key] -= val

        cmd.faction.structures.append(gmap.cells[position])
        structures.append(gmap.cells[position])
        succesful_build = True

    if cmd.utype == "miner" and cmd.faction.can_build_structure(params.STRUCTURE_COST["miner"]) and gmap.cells[position].terrain == cell_terrain.Terrain.Stone:
        gmap.cells[position] = Cell(cell_terrain.Terrain.Miner, position, cmd.faction)
        building_pos.append((position, cmd.utype))

        
        for key, val in params.STRUCTURE_COST["miner"].items():
            cmd.faction.materials[key] -= val

        cmd.faction.structures.append(gmap.cells[position])
        structures.append(gmap.cells[position])
        succesful_build = True

    if succesful_build: gmap.rerender()

    return building_pos


# RunMoveCommand:
# The function that handles MoveUnitCommands.
def RunMoveCommand(cmd, factions, unit_dict, cities, gmap, move_list):

    if cmd.unit_id in move_list:
        return
    else:
        move_list.append(cmd.unit_id)
    
    # Find the unit
    ulist = unit_dict.by_faction[cmd.faction_id]
    theunit = None
    for u in ulist:
        if u.ID == cmd.unit_id:
            theunit = u
            break

    # Unit might have died before it's command could be run.
    if theunit is None:
        return

    # Get new position
    delta = vec2.Vec2(0, 0)
    try:
        delta = vec2.MOVES[cmd.direction]
    except KeyError:
        print(f"{cmd.direction} is not a valid direction")
        return
    
    new_pos = theunit.pos + delta
    
    # Modulo the new pos to the map size
    new_pos.mod(gmap.width, gmap.height)

    # Check if new_pos is free.
    combat_pos = None
    move_successful = False
    if gmap.cells[new_pos].terrain == cell_terrain.Terrain.Water:
        pass
    elif unit_dict.is_pos_free(new_pos):
        old_pos = theunit.pos
        theunit.pos = new_pos
        unit_dict.move_unit(u, old_pos, new_pos)
        move_successful = True
    # Occupied by a unit
    else:
        other_unit = unit_dict.by_pos[new_pos]

        # Is the other unit an enemy?
        if other_unit.faction_id != theunit.faction_id:
            space_now_free = RunCombat(theunit, other_unit, cmd, factions, unit_dict, cities, gmap)
            
            # Perhaps combat freed the space.
            # if so, move.
            if space_now_free:
                combat_pos = new_pos
                old_pos = theunit.pos
                theunit.pos = new_pos
                unit_dict.move_unit(u, old_pos, new_pos)
                move_successful = True
            
               

            if theunit.health <= 0:
                combat_pos = theunit.pos
                theunit.dead = True

                # This commander had another unit die
                if other_unit.faction_id in factions and factions[other_unit.faction_id].commander:
                    factions[other_unit.faction_id].commander.soldiers_killed += 1

                if other_unit.general_following:
                    other_unit.general_following.soldiers_killed += 1
                
                if theunit.general_following:
                    theunit.general_following.soldiers_lost += 1

                if factions[theunit.faction_id].commander:
                    factions[theunit.faction_id].commander.soldiers_lost += 1 
            
            if other_unit.health <= 0:
                other_unit.dead = True
        
                 # This commander had another unit die
                if other_unit.faction_id in factions and factions[other_unit.faction_id].commander:
                    factions[other_unit.faction_id].commander.soldiers_lost += 1

                if other_unit.general_following:
                    other_unit.general_following.soldiers_lost += 1
                
                if theunit.general_following:
                    theunit.general_following.soldiers_killed += 1
                
                if factions[theunit.faction_id].commander:
                    factions[theunit.faction_id].commander.soldiers_killed += 1 

    # Check if the move conquerored a city
    if move_successful:
        theunit.moving = True

    return combat_pos

# RunBuildCommand:
# Executes the BuildUnitCommand.
def RunBuildCommand(cmd, factions, unit_dict, cities, gmap):
    # How much does the unit cost?
    f = factions[cmd.faction_id]
    cost = unit.get_unit_cost(cmd.utype)
    materials = cmd.upgrade_materials



    # Look for the city
    for c in cities:
        if c.ID == cmd.city_id and c.faction_id == f.ID:

            # If there's no unit in the city, build.
            # Add to the unit dictionary and charge
            # the faction for its purchase.
            if unit_dict.is_pos_free(c.pos) and f.can_build_unit(cost):
                
                health_buffs, damage_buff = 0, 0
                if f.can_build_structure({"wood": materials["wood"]}):
                    damage_buff += int(materials["wood"]**0.5 + math.log1p(materials["wood"]))
                    f.materials["wood"] -= materials['wood']

                if f.can_build_structure({"stone": materials["stone"]}):
                    health_buffs = int(materials["stone"]**0.5 +  math.log1p(materials["stone"]))
                    f.materials["stone"] -= materials['stone']

                uid = f.get_next_unit_id()
                new_unit = unit.Unit(uid, cmd.utype,
                                        f.ID,
                                        copy.copy(c.pos),
                                        unit.UNIT_HEALTH[cmd.utype] + health_buffs,
                                        0, damage_buff)
                new_unit.creation_age = f.age
                unit_dict.add_unit(new_unit)

                f.materials["gold"] -= cost

# RunCombat:
# Called by the MoveUnitCommand if a unit tries to move into a cell
# containing a unit of the opposing faction.
#
# Combat is mutually destructive in that both units damage each other.
# and can both die. You are welcome to edit this if you want combat
# to work differently.
#
# Returns whether the defender was destroyed (and the attacker not)
# allowing the attacker to move into the cell.
def RunCombat(attacker, defender, cmd, factions, unit_dict, cities, gmap):
    # Find the terrain each unit stands in.
    att_cell = gmap.get_cell(attacker.pos)
    def_cell = gmap.get_cell(defender.pos)

    # Make the combat rolls.
    att_roll = attacker.roll(defender.utype) + attacker.damage_buff
    def_roll = defender.roll(attacker.utype) + defender.damage_buff

    # Add terrain modifiers.
    att_roll += att_cell.get_attack_mod()
    def_roll += def_cell.get_defense_mod()

    # Damage health.
    defender.health -= att_roll
    attacker.health -= def_roll

    # Debug output
    # print(f"Combat - {attacker.faction_id}: {att_roll} v {defender.faction_id}: {def_roll}")

    # Did anyone die? If the defender died and the attacker
    # did not, return that the attacker is free to move into
    # the cell.
    can_move = False
    if defender.health <= 0:
        #print(f"   {defender.faction_id} died")
        unit_dict.remove_unit(defender)
        can_move = True

        if defender.general_following and defender in defender.general_following.soldiers_commanding:
            defender.general_following.soldiers_commanding.remove(defender)

    if attacker.health <= 0:
        #print(f"   {attacker.faction_id} died")
        unit_dict.remove_unit(attacker)
        can_move = False

        if attacker.general_following and attacker in attacker.general_following.soldiers_commanding:
            attacker.general_following.soldiers_commanding.remove(attacker)

    return can_move
            
# ###########################################################
# THE UNIT DICTIONARY
# Modify at your own risk. Probably no need.
# ###########################################################
class UnitDict:
    def __init__(self, faction_ids):
        self.by_pos = {}
        self.by_faction = {}
        for fid in faction_ids:
            self.by_faction[fid] = []
    def add_unit_by_pos(self, u, pos):
        if pos not in self.by_pos:
            self.by_pos[pos] = u
    def remove_unit_by_pos(self, u, pos):
        if pos in self.by_pos and u == self.by_pos[pos]:
            del self.by_pos[pos]
    def move_unit(self, u, old_pos, new_pos):
        self.remove_unit_by_pos(u, old_pos)
        self.add_unit_by_pos(u, new_pos)
    def add_unit(self, u):
        self.by_faction[u.faction_id].append(u)
        self.add_unit_by_pos(u, u.pos)
    def remove_unit(self, u):
        if u.faction_id not in self.by_faction or u not in self.by_faction[u.faction_id]: return 

        self.by_faction[u.faction_id].remove(u)
        self.remove_unit_by_pos(u, u.pos)
    def is_pos_free(self, pos):
        return pos not in self.by_pos


def CheckForGameOver(cities, units):
    faction_ids_with_cities = []
    for c in cities:
        if c.faction_id not in faction_ids_with_cities:
            faction_ids_with_cities.append(c.faction_id)

    units_by_faction = {key: len(value) for key, value in units.by_faction.items()}
    units_sum = sum(units_by_faction.values())
        
    return len(faction_ids_with_cities) == 1 and units_sum == units_by_faction[faction_ids_with_cities[0]] , faction_ids_with_cities[0]
        
    
# ###########################################################3
# GAME LOOP
# Where the magic happens.
# I've marked below where you might want to edit things
# for different reasons.
# ###########################################################

def handle_mouse_functions(offset, zoom):
    rel, pressed = pygame.mouse.get_rel(), pygame.mouse.get_pressed()
   

    if pressed[0]:
        offset[0] += -rel[0] * (1 / zoom)
        offset[1] += -rel[1] * (1 / zoom)

import time

def post_turn_takeovers(cities, unit_dict, factions, gmap, structures):
    for c in cities:
        if c.pos in unit_dict.by_pos and c.faction_id != unit_dict.by_pos[c.pos].faction_id:
            for general in factions[c.faction_id].generals:
                general.cities_lost += 1
            
            unit = unit_dict.by_pos[c.pos]
            c.faction_id = unit.faction_id

            if unit.general_following:
                unit.general_following.cities_gained += 1

        

    for cell in structures:
        if cell.pos in unit_dict.by_pos:
            faction_id = unit_dict.by_pos[cell.pos].faction_id
            if factions[faction_id] == cell.owned_by: continue

            if cell.owned_by and cell.owned_by.ID in factions: 
                cell.owned_by.structures.remove(cell)
            if cell not in factions[faction_id].structures: factions[faction_id].structures.append(cell)
            cell.owned_by = factions[faction_id]

def kill(unit, unit_dict):
    unit.dead = True

    unit_dict.remove_unit(unit)

    if unit.general_following:
        if unit in unit.general_following.soldiers_commanding: unit.general_following.soldiers_commanding.remove(unit)
        unit.general_following.soldiers_lost += 1
   

def GameLoop(display, drawn=True, top_models=[], model_eval=None):
    if drawn: 
        winw, winh = pygame.display.get_window_size()
        desired_scroll = display.zoom


    gmap = gen_game_map(50, 50)
    move_cache = {}
    
    factions = gen_factions(gmap, model_eval)
    cities = gen_cities(gmap, list(factions.keys()))
    unit_dict = UnitDict(list(factions.keys()))
    combat_positions = []
    building_positions = []

    flow_field_queue = []
    for city in cities:
        pos = (city.pos.x, city.pos.y)
        flow_field_queue.append(pos)

    for v, c in gmap.cell_render_queue:
        if c.terrain in (cell_terrain.Terrain.Forest, cell_terrain.Terrain.Stone):
            flow_field_queue.append((v.x, v.y))

    def run_turn(factions, gmap, cities_by_faction, unit_dict, move_cache, cities, top_models, structures):
        commands, move_cache = Turn(factions, gmap, cities_by_faction,
                                    unit_dict.by_faction, move_cache, unit_dict, top_models)
        combat_positions, building_positions = RunAllCommands(commands, factions, unit_dict, cities, gmap, structures)
        post_turn_takeovers(cities, unit_dict, factions, gmap, structures)

        return move_cache, combat_positions, building_positions

    # Starting game speed (real time between turns) in milliseconds.
    current_turn_time_ms = 0
    speed = 12
    ticks = 0
    turn = 1
    GAME_OVER = False
    pressed_time = 0
    selected_unit = None
    dragging, hover = False, False
    all_stats = {}
    structures = []
    while not drawn or display.run:
        if drawn: 
            pos, pressed = pygame.mouse.get_pos(), pygame.mouse.get_pressed()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    display.run = False
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        display.run = False
                        sys.exit()
                    elif event.key == pygame.K_LEFT:

                        # Lower if you want a faster game speed.
                        
                        speed = speed // 2
                        speed = max(speed, 8)
                    elif event.key == pygame.K_RIGHT:

                        # Increase if you want a slower game speed.
                        if speed < 4096:
                            speed = speed * 2

                    elif event.key == pygame.K_r:
                        return top_models
                        
                elif event.type == pygame.MOUSEWHEEL:
                    if pos[0] > winw - 200 and pos[0] < winw - 10 and pos[1] > 10 and pos[1] < winh - 25:
                        display.menu_scroll += event.y * 10
                        display.menu_scroll = max(display.menu_scroll, 0)

                        
                    else:
                        scroll_val = min(max(event.y, -3), 3)/6 + 1
                        desired_scroll = max(min(scroll_val * desired_scroll, 2.5), 0.5)
                        

                elif event.type == pygame.VIDEORESIZE:
                    display.width, display.height = event.w, event.h
                    display.screen = pygame.display.set_mode((event.w, event.h),
                                                pygame.RESIZABLE)

                    winw, winh = event.w, event.h


            if display.zoom != desired_scroll:
        
                difference = display.zoom - desired_scroll
                change = difference * 0.25

                if abs(change) < 0.001:
                    display.zoom = desired_scroll
                else:
                    display.zoom -= change

                display.zoom = max(min(display.zoom, 2.5), 0.5)
        
            if pressed[0] and pressed_time == 0: pressed_time = time.perf_counter()
            if selected_unit and not pressed[0] and time.perf_counter() - pressed_time < 0.1: selected_unit = None
            if not pressed[0] and pressed_time != 0: pressed_time = 0
            
            if selected_unit and selected_unit.dead == True: selected_unit = None
    

            handle_mouse_functions(display.camera_pos, display.zoom)

            

        started_turn = turn
        while (ticks >= speed or not drawn) and not GAME_OVER and turn - started_turn < 200:
            ticks -= speed
            cities_by_faction = {}
            delete_factions = []
            for fid, f in factions.items():
                faction_cities = FactionPreTurn(cities, f)
                cities_by_faction[fid] = faction_cities

                if len(faction_cities) == 0 and len(unit_dict.by_faction[fid]) == 0:
                    for structure in f.structures:
                        structure.owned_by = None
                    
                    delete_factions.append(fid)
            
            for fid in delete_factions: 
                del factions[fid]
                del unit_dict.by_faction[fid]


            move_cache, combat_positions, building_positions = run_turn(factions, gmap, cities_by_faction, unit_dict, move_cache, cities, top_models, structures)
            
            turn += 1

            game_over = CheckForGameOver(cities, unit_dict)
            if game_over[0]:
                if params.MODE == "evolution":
                    return factions[game_over[1]].generals[0]


             
                if params.MODE == "endless":
                    for unit in unit_dict.by_faction[game_over[1]]:
                        if unit.rank == "general": 
                            unit.defecting = True
                    
                if params.MODE == "versus":
                    GAME_OVER = True
                    return factions[game_over[1]].color


            kill_list = []
            for fid, ulist in unit_dict.by_faction.items():
                for u in ulist:

                    # If a unit stays still for 30 rounds they die
                    if u.last_pos and u.last_pos == u.pos:
                        u.stuck_rounds += 1
                    else:
                        u.stuck_rounds = 0

                    if u.stuck_rounds > 30 or factions[fid].age - u.creation_age > 300:
                        kill_list.append(u)
                    else:
                        u.last_pos = u.pos

            for unit in kill_list:
                kill(unit, unit_dict)

        # Move units toward their directed pos so they don't move by teleportation
        if drawn:
            display.screen.fill("#121212")

            hover = False
            for fid, ulist in unit_dict.by_faction.items():
                for u in ulist:

                    if u.moving:
                        wanted_pos = u.world_to_cord(u.pos)
                        
                        dist = abs(wanted_pos[0] - u.display_pos[0]) + abs(wanted_pos[1] - u.display_pos[1]) 
                
                        if speed >= 128:
                            UNIT_SPEED = dist * 0.2
                        else:
                            UNIT_SPEED = dist * 0.5
                            
                        if dist > 500 or dist < 5:
                            u.display_pos = wanted_pos
                            u.moving = False
                        else:
        
                        
                            angle = math.atan2(wanted_pos[1] - u.display_pos[1], wanted_pos[0] - u.display_pos[0])
                            x_delta, y_delta = math.cos(angle) * UNIT_SPEED, math.sin(angle) * UNIT_SPEED
                            
                            u.display_pos[0] += x_delta
                            u.display_pos[1] += y_delta


                    x, y, size, visible = display.get_unit_actual_pos(u)
                    #Selected
                    if visible and pos[0] >= x and pos[0] <= x + size and pos[1] >= y and pos[1] <= size + y and pressed[0] and time.perf_counter() - pressed_time < 0.1:
                        selected_unit = u
                        pressed_time = time.perf_counter() - 100
                    #hovering
                    elif visible and pos[0] >= x and pos[0] <= x + size and pos[1] >= y and pos[1] <= size + y:
                        hover = True
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                        u.additional_size = 15
                    else:
                        u.additional_size = 0

                    if selected_unit and u == selected_unit:
                        u.additional_size = 30

            
            if hover:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            
            display.create_animation(combat_positions, 3, "battle_animation")
            display.create_animation([item[0] for item in building_positions if item[1] == "woodcutter"], 2, "woodcutter_upgrade")
            display.create_animation([item[0] for item in building_positions if item[1] == "miner"], 2, "miner_upgrade")
            display.draw_map(gmap)
            display.draw_cities(cities, factions)
            display.draw_units(unit_dict, factions)

            building_positions, combat_positions = [], []

            # ###########################################3
            # RIGHT_SIDE UI
            retVal, speed = display.draw_ui(turn, factions, unit_dict, cities, speed, selected_unit)

            if retVal == "reset":
                return "reset"


            
            pygame.display.flip()

            if current_turn_time_ms:
                current_turn_time_ms = time.perf_counter() - current_turn_time_ms
                if flow_field_queue and (len(move_cache) < 20 or current_turn_time_ms < 0.02):
                    pos = flow_field_queue.pop(0)
                    if pos not in move_cache: 
                        move_cache[pos] = ai.create_flow_field(pos, gmap)

            


            dt = display.clock.tick(60)
            ticks += dt
            display.ticks += dt
            current_turn_time_ms = time.perf_counter()


from collections import defaultdict
def main(display=None):
    random.seed(None)
    winw, winh = 1400, 800
    drawn = True

    if not display and drawn:
        display = isometricDisplay.init_display(winw, winh)
    record = defaultdict(lambda: 0)
    winner = []
    top_winners = {}
    models_by_id = {}
    saved = set([])
    while True:
        top_models = []
        if params.MODE == "evolution":
            winner = []
            if top_winners:
                for model_id in random.choices(list(top_winners.keys()), weights=list(top_winners.values()), k=4):
                    winner.append((1, models_by_id[model_id], 1))

            top_models = winner

        winner = GameLoop(display, drawn=drawn, top_models=top_models)

        if winner == "reset":
            record = defaultdict(lambda: 0)
            top_winners = {}
            models_by_id = {}
            saved = set([])

        
        if display: display.clear() # Removing extra rendered animations

        if params.MODE == "evolution" and winner and winner != "reset" and winner.NNModel:
            ID = winner.NNModel.id
            
            if ID not in top_winners: top_winners[ID] = 0
            top_winners[ID] += 1
            models_by_id[ID] = winner.NNModel

            for winner_id in winner.NNModel.parents:
                top_winners[winner_id] += 0.25
    
                if top_winners[winner_id] > 5 and ID not in saved:
                    saved.add(winner_id)
                    winner.NNModel.save(f"model_saved/model_{len(saved)}.npz")

        
        if winner != "reset" and params.MODE == "versus" and type(winner) == tuple:
            record[winner] += 1
            print(f"\nAI: {record[(200, 0, 0)]}")
            print(f"Aggressive Agent: {record[(0, 0, 200)]}")

if __name__ == "__main__":
    main()
