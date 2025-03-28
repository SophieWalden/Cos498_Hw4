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

# ###################################################################
# DISPLAY
# The display part of the engine. Unless you want to mess with
# the look and feel (add sprites or something) you probably don't need
# to mess with anything in this section
# ####################################################################
global TILE_X_OFFSET, TILE_Y_OFFSET
TILE_X_OFFSET = 24
TILE_Y_OFFSET = 12
IMAGE_SIZE = 50

class Animation:
    def __init__(self, name, images, id=-1, ticks_between_frames=10):
        self.name, self.images, self.ticks_between_frames = name, self.load_animation(name, images), ticks_between_frames
        self.index, self.ticks = 0, 0
        self.finished = False
        self.id = id
        self.time_since_last_render = time.perf_counter()

    def load_animation(self, name, images):
        animation = []
        for key, value in images.items():
            if key.startswith(name):
                animation.append((key, value))
        
        animation.sort(key = lambda item: int(item[0][len(name):]))
        return [item[1] for item in animation]
    
    def get_next_image(self, speed):
        image = self.images[int(self.ticks // self.ticks_between_frames)]

        self.ticks += speed
        if self.ticks >= len(self.images) * self.ticks_between_frames: self.finished = True

        return image

MENU_BACKGROUND = (50, 57, 61)
MENU_OUTLINE = "#464646"
TEXT_COLOR = "white"
TILE_MAP = {cell_terrain.Terrain.Open: "open_tile", cell_terrain.Terrain.Forest: "forest_tile",
                    cell_terrain.Terrain.Woodcutter: "woodcutter_tile", cell_terrain.Terrain.Water: "water_tile",
                    cell_terrain.Terrain.Stone: "stone_tile", cell_terrain.Terrain.Miner: "miner_tile"}
class Display:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.run = True
        self.delta = 0
        self.font = None
        self.map_cell_size = 20
        self.images = self.load_images()
        self.zoom = 0.6
        self.camera_pos = [-700, 100]
        self.width, self.height = pygame.display.get_window_size()
        self.queued_animations = defaultdict(lambda: [])
        self.map = None
        self.debug_id = 0
        # self.animations = {"battle": Animation("battle_animation", self.images)}

    # fmt: off
    def draw_gobj(self, gobj):
        pygame.draw.circle(
            self.screen,
            gobj.color,
            gobj.pos(),
            gobj.radius)

    def draw_text(self, msg, x, y, color):
        surface, rect = self.font.render(msg, color)
        self.screen.blit(surface, (x, y))

    def draw_line(self, p1, p2, color, width=1):
        pygame.draw.line(
            self.screen,
            color,
            p1,
            p2,
            width)

    def draw_map(self, gmap):
        for v, c in gmap.cell_render_queue:
            image = None
       
            if c.terrain not in TILE_MAP: return
            
            image = self.images[TILE_MAP[c.terrain]]
            
         
            x, y = self.world_to_cord((v.x, v.y))
            self.blit(image, x, y, 50)

            # Render animation on top of each tile
            indexes_to_remove = []
            for i, (pos, animation, animation_speed) in enumerate(self.queued_animations[(v.x, v.y)]):
                image = animation.get_next_image(animation_speed)

                self.blit(image, pos[0], pos[1], 50)
                if animation.finished: indexes_to_remove.append(i) 

            for index in indexes_to_remove[::-1]:
                self.queued_animations[(v.x, v.y)].pop(index)
         

            

    def draw_cities(self, cities, factions):
        for c in cities:
            f = factions[c.faction_id]
            self.outline_tile(c.pos.x, c.pos.y, f.color)

    def draw_units(self, unit_dict, factions):
        for fid, ulist in unit_dict.by_faction.items():
            fcolor = factions[fid].color
            for u in ulist:
                image = {"P": self.images["paper_unit"], "R": self.images["rock_unit"], "S": self.images["scissor_unit"]}[u.utype]
                image = image.copy()
         
                image.fill((fcolor[0], fcolor[1], fcolor[2], 0.3), special_flags = pygame.BLEND_ADD)

                x, y = u.display_pos

                size = 30
                if u.rank == "general": size = 50
                elif u.rank == "commander": size = 70
                size += u.additional_size

                self.blit(image, x - ((size - 30) // 2), y - ((size - 30) // 2), size)



    def world_to_cord(self, pos):
        """Translates 2D array cords into cords for isometric rendering"""
        x = pos[0] * TILE_X_OFFSET - pos[1] * TILE_X_OFFSET
        y = pos[0] * TILE_Y_OFFSET + pos[1] * TILE_Y_OFFSET

        return (x, y)

    def outline_tile(self, x, y, color):
        x, y = self.world_to_cord((x, y))
        outline = self.images["tile_outline"].copy()
        
        outline.fill(color, special_flags = pygame.BLEND_MULT)
        self.blit(outline, x, y, 50)
        

    def blit(self, image, x, y, size):
        adjusted_x = x - self.camera_pos[0]
        adjusted_y = y - self.camera_pos[1]

        adjusted_x *= self.zoom
        adjusted_y *= self.zoom       
        

        if adjusted_x > -500 and adjusted_x < self.width and adjusted_y > -500 and adjusted_y < self.height:
            adjusted_image = pygame.transform.scale(image, (size * self.zoom, size * self.zoom))
            self.screen.blit(adjusted_image, (adjusted_x, adjusted_y))

    def create_animation(self, positions, speed, name):
        for position in positions:
            ID = None
            if name == "miner_upgrade":
                ID = self.debug_id
                self.debug_id += 1

            self.queued_animations[(position.x, position.y)].append([self.world_to_cord([position.x, position.y]), Animation(name, self.images, id=ID), speed])

    def load_images(self):
        images = {}
        for filename in os.listdir("images"):
            full_path = f"images/{filename}"
            key = filename[:filename.index(".")]

            images[key] = pygame.image.load(full_path).convert_alpha()

        return images
    
    def draw_ui(self, turn, factions, units, cities, unit_selected=None):

        winw, winh = pygame.display.get_window_size()

        self.screen.blit(pygame.transform.scale(self.images["clock_ui"], (300, 150)), (0, 0))
        # self.draw_rect_advanced(MENU_BACKGROUND, 150, 10, 10, 75 + 11 * len(str(turn)), 25, (MENU_OUTLINE, 3))
        self.draw_text(f"{turn:{' '}>18}", 20, 15, (180, 180, 180))

        faction_colors = {key: value.color for key, value in factions.items()}
        units_by_faction = {key: len(value) for key, value in units.by_faction.items()}

        cities_by_faction = {key: sum(city.faction_id == value.ID for city in cities) for key, value in factions.items()}
        cities_sum = len(cities)



        if cities_sum > 0:
            cities_normalized = {key: value/cities_sum for key, value in cities_by_faction.items()}

            x = 315
            for i, (key, value) in enumerate(cities_normalized.items()):
                color = faction_colors[key]

                self.draw_rect_advanced(self.darken(color, 1.5), 200,x, 10, int(value * (winw / 1.7)), 10, (self.darken(color, 3), 2))
                x += int(value * (winw / 1.7))
        else:
            pygame.draw.rect(self.screen, (100, 100, 100), (200, 10, winw // 1.7, 5))


        sidebar_mode = "general"
        if unit_selected: sidebar_mode = "unit"

        self.draw_rect_advanced(MENU_BACKGROUND, 200, winw - 200, 10, 190, winh - 200, (MENU_OUTLINE, 15))

        y = 25
        if sidebar_mode == "general":
            menu_surface = pygame.Surface((190, winh - 200), pygame.SRCALPHA)

            for fid, faction in factions.items():
                if units_by_faction[fid] == 0: continue

                pygame.draw.rect(menu_surface, self.darken(faction.color, 1.5), (10, y, 20, 20), 0)
                pygame.draw.rect(menu_surface, (100, 100, 100), (35, y, 135, 5))

                y += 25
                
                # Draw Unit Counts  
                surface, rect = self.font.render(f"Units: {units_by_faction[fid]}", TEXT_COLOR)
                menu_surface.blit(surface, (10, y))

                y += 25

                # Draw City Counts
                surface, rect = self.font.render(f"Cities: {cities_by_faction[fid]}", TEXT_COLOR)
                menu_surface.blit(surface, (10, y))

                y += 25

                surface, rect = self.font.render(f"Gold: {faction.money}", TEXT_COLOR)
                menu_surface.blit(surface, (10, y))

                y += 25

        elif sidebar_mode == "unit":
            menu_surface = pygame.Surface((190, winh - 200), pygame.SRCALPHA)

            surface, rect = self.font.render(f"Pos: {unit_selected.pos.x} {unit_selected.pos.y}", TEXT_COLOR)
            menu_surface.blit(surface, (10, y))
            y += 25

            surface, rect = self.font.render(f"Type: {unit_selected.utype}", TEXT_COLOR)
            menu_surface.blit(surface, (10, y))
            y += 25

            surface, rect = self.font.render(f"Rank: {unit_selected.rank}", TEXT_COLOR)
            menu_surface.blit(surface, (10, y))
            y += 25

        self.screen.blit(menu_surface, ((winw - 200, 10)))

    def draw_rect_advanced(self, color, opacity, x, y, width, height, outline=None):
        surface = pygame.Surface((width, height))
        surface.set_alpha(opacity)
        if not outline: surface.fill((color))
        else:
            outline_color, width = outline
            surface.fill(outline_color)
            surface.fill(color, surface.get_rect().inflate(-width, -width))

        self.screen.blit(surface, (x, y))

    def darken(self, color, strength):
        return [pixel_value / strength for pixel_value in color]
    
    def get_unit_actual_pos(self, unit):
        display_pos = unit.display_pos
        size = 30
        if unit.rank == "general": size = 50
        elif unit.rank == "commander": size = 70
        size += unit.additional_size

        x, y = display_pos[0] - ((size - 30) // 2), display_pos[1] - ((size - 30) // 2)

        adjusted_x = x - self.camera_pos[0]
        adjusted_y = y - self.camera_pos[1]

        adjusted_x *= self.zoom
        adjusted_y *= self.zoom       
        
        visible = adjusted_x > -500 and adjusted_x < self.width and adjusted_y > -500 and adjusted_y < self.height
        size *= self.zoom
           
        return adjusted_x, adjusted_y, size, visible


def init_display(sw, sh):
    pygame.init()
    screen = pygame.display.set_mode((sw, sh), pygame.RESIZABLE)
    pygame.display.set_caption('AI Faction Simulation')
    clock = pygame.time.Clock()
    display = Display(screen, clock)
    display.font = pygame.freetype.Font('JetBrainsMono-Regular.ttf', 18)
    pygame.key.set_repeat(200, 100)
    return display

# ###############################################################
# GAME GENERATION FUCNTIONS
# This section generates the map, factions and cities.
# If you add things to the game (additional terrain, factions,
# city types, etc), you'll need to edit these functions to have
# them placed on the map
# ###############################################################
def gen_game_map(width, height):
    return game_map.GameMap(width, height)

POSSIBLE_FACTIONS = [
    ["Red", (255, 0, 0)],
    ["Blue", (0, 0, 255)],
    ["Green", (0, 255, 0)],
    ["Yellow", (255, 255, 0)],
    ["Orange", (255, 165, 0)],
    ["Purple", (128, 0, 128)],
    ["Cyan", (0, 255, 255)],
    ["Magenta", (255, 0, 255)],
    ["Pink", (255, 192, 203)],
    ["Brown", (139, 69, 19)],
    ["Black", (0, 0, 0)],
    ["White", (255, 255, 255)],
    ["Gray", (169, 169, 169)],
    ["Violet", (238, 130, 238)],
    ["Indigo", (75, 0, 130)],
    ["Turquoise", (64, 224, 208)],
    ["Teal", (0, 128, 128)],
    ["Lime", (0, 255, 0)]]


def gen_factions(gmap):

    factions = {}

    while len(factions) != 3:
        name, color = POSSIBLE_FACTIONS[len(factions)]
        factions[name] = faction.Faction(
            name, params.STARTING_FACTION_MONEY,
            ai.AI(), color, len(factions) * 999999999
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
            faction.money += income
    
    # #####################################################
    # CITY DATA
    for c in cities:
        if c.faction_id == faction.ID:
            faction_cities.append(c)

    return faction_cities
    
# Turn:
# The actual turn taking function. Calls each faction's ai
# Gathers all the commands in a giant list and returns it.
def Turn(factions, gmap, cities_by_faction, units_by_faction, move_cache):
    commands = []

    for fid, f in factions.items():
        cmds, move_cache = f.run_ai(factions, cities_by_faction, units_by_faction, gmap, move_cache) 
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
def RunAllCommands(commands, factions, unit_dict, cities, gmap):

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
            building_pos = RunBuildStructureCommand(cmd, gmap)
            if building_pos: buidling_positions.extend(building_pos)
        else:
            print(f"Bad command type: {type(cmd)}")

    return combat_positions, buidling_positions

def RunBuildStructureCommand(cmd, gmap):
    building_pos = []

    position = vec2.Vec2(cmd.pos[0], cmd.pos[1])

    if cmd.utype == "woodcutter" and gmap.cells[position].terrain == cell_terrain.Terrain.Forest:
        gmap.cells[position] = Cell(cell_terrain.Terrain.Woodcutter)
        building_pos.append((position, cmd.utype))
    if cmd.utype == "miner" and gmap.cells[position].terrain == cell_terrain.Terrain.Stone:
        gmap.cells[position] = Cell(cell_terrain.Terrain.Miner)
        building_pos.append((position, cmd.utype))
    
    gmap.rerender()

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
            
            if other_unit.health <= 0:
                other_unit.dead = True
        
    # Check if the move conquerored a city
    if move_successful:
        for c in cities:
            if new_pos == c.pos:
                c.faction_id = u.faction_id
                break

    if move_successful:
        theunit.moving = True

    return combat_pos

# RunBuildCommand:
# Executes the BuildUnitCommand.
def RunBuildCommand(cmd, factions, unit_dict, cities, gmap):
    # How much does the unit cost?
    f = factions[cmd.faction_id]
    cost = unit.get_unit_cost(cmd.utype)



    # Look for the city
    for c in cities:
        if c.ID == cmd.city_id and c.faction_id == f.ID:

            # If there's no unit in the city, build.
            # Add to the unit dictionary and charge
            # the faction for its purchase.
            if unit_dict.is_pos_free(c.pos) and f.can_build_unit(cost):

                uid = f.get_next_unit_id()
                new_unit = unit.Unit(uid, cmd.utype,
                                        f.ID,
                                        copy.copy(c.pos),
                                        unit.UNIT_HEALTH[cmd.utype],
                                        0)
                unit_dict.add_unit(new_unit)

                f.money -= cost

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
    att_roll = attacker.roll(defender.utype)
    def_roll = defender.roll(attacker.utype)

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
    if attacker.health <= 0:
        #print(f"   {attacker.faction_id} died")
        unit_dict.remove_unit(attacker)
        can_move = False

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
        if u == self.by_pos[pos]:
            del self.by_pos[pos]
    def move_unit(self, u, old_pos, new_pos):
        self.remove_unit_by_pos(u, old_pos)
        self.add_unit_by_pos(u, new_pos)
    def add_unit(self, u):
        self.by_faction[u.faction_id].append(u)
        self.add_unit_by_pos(u, u.pos)
    def remove_unit(self, u):
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

def handle_mouse_functions(offset):
    rel, pressed = pygame.mouse.get_rel(), pygame.mouse.get_pressed()

    if pressed[0]:
        offset[0] += -rel[0] * 1.6
        offset[1] += -rel[1] * 1.5

import time

def GameLoop(display):
    global TILE_X_OFFSET, TILE_Y_OFFSET
    
    winw, winh = pygame.display.get_window_size()

    # Width and Height (in cells) of the game map. If you want
    # a bigger/smaller map you will need to coordinate these values
    # with two other things.
    # - The window size below in main().
    # - The map_cell_size given in the Display class above.
    gmap = gen_game_map(50, 50)
    move_cache = {}
    
    factions = gen_factions(gmap)
    cities = gen_cities(gmap, list(factions.keys()))
    unit_dict = UnitDict(list(factions.keys()))
    combat_positions = []
    building_positions = []


    # Starting game speed (real time between turns) in milliseconds.
    speed = 1024
    ticks = 0
    turn = 1
    GAME_OVER = False
    pressed_time = 0
    selected_unit = None
    desired_scroll = display.zoom
    while display.run:

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
                    if speed > 64:
                        speed = speed // 2
                elif event.key == pygame.K_RIGHT:

                    # Increase if you want a slower game speed.
                    if speed < 4096:
                        speed = speed * 2

                elif event.key == pygame.K_r:
                    return 
                    
                
            elif event.type == pygame.MOUSEWHEEL:
                scroll_val = min(max(event.y, -3), 3)/6 + 1
                desired_scroll = max(min(scroll_val * desired_scroll, 10), 0.1)
                

            elif event.type == pygame.VIDEORESIZE:
                display.width, display.height = event.w, event.h
                display.screen = pygame.display.set_mode((event.w, event.h),
                                              pygame.RESIZABLE)


        if display.zoom != desired_scroll:
      
            difference = display.zoom - desired_scroll
            change = difference * 0.25
            display.zoom -= change

            display.zoom = max(min(display.zoom, 10), 0.1)
    
        pos, pressed = pygame.mouse.get_pos(), pygame.mouse.get_pressed()
        if pressed[0] and pressed_time == 0: pressed_time = time.perf_counter()
        if selected_unit and not pressed[0] and time.perf_counter() - pressed_time < 0.1: selected_unit = None
        if not pressed[0] and pressed_time != 0: pressed_time = 0
        
        if selected_unit and selected_unit.dead == True: selected_unit = None
   

        handle_mouse_functions(display.camera_pos)

        display.screen.fill("#121212")

        if ticks >= speed and not GAME_OVER:
            ticks = 0
            cities_by_faction = {}
            for fid, f in factions.items():
                faction_cities = FactionPreTurn(cities, f)
                cities_by_faction[fid] = faction_cities

            commands, move_cache = Turn(factions, gmap,
                            cities_by_faction,
                            unit_dict.by_faction, move_cache)
            combat_positions, building_positions = RunAllCommands(commands, factions, unit_dict, cities, gmap)
            turn += 1

            game_over = CheckForGameOver(cities, unit_dict)
            if game_over[0]:
                print(f"Winning faction: {game_over[1]}")
                GAME_OVER = True


        # Move units toward their directed pos so they don't move by teleportation
        for fid, ulist in unit_dict.by_faction.items():
            for u in ulist:

                if u.moving:
                    wanted_pos = u.world_to_cord(u.pos)
                    
                    dist = abs(wanted_pos[0] - u.display_pos[0]) + abs(wanted_pos[1] - u.display_pos[1]) 
                    UNIT_SPEED = 1000/(speed+1)
                    if dist <= UNIT_SPEED * 2 or dist > 500:
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
                    u.additional_size = 15
                else:
                    u.additional_size = 0

                if selected_unit and u == selected_unit:
                    u.additional_size = 30
                   


        
        display.create_animation(combat_positions, 1.5, "battle_animation")
        display.create_animation([item[0] for item in building_positions if item[1] == "woodcutter"], 2, "woodcutter_upgrade")
        display.create_animation([item[0] for item in building_positions if item[1] == "miner"], 2, "miner_upgrade")
        display.draw_map(gmap)
        display.draw_cities(cities, factions)
        display.draw_units(unit_dict, factions)

        building_positions, combat_positions = [], []

        # ###########################################3
        # RIGHT_SIDE UI
        display.draw_ui(turn, factions, unit_dict, cities, selected_unit)
 


        pygame.display.flip()
        dt = display.clock.tick(60)
        ticks += dt


def main():
    random.seed(None)

    try:
        winw, winh = pygame.display.get_window_size()
    except Exception:
        winw, winh = 1400, 800
 
    display = init_display(winw, winh)
    GameLoop(display)

    main()


if __name__ == "__main__":
    main()
