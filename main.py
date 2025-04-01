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
from structure import Structure
from faction import Faction
import cProfile, pstats
from collections import OrderedDict

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

class LRUCache:
    def __init__(self, max_size=250):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key) 
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False) 
        self.cache[key] = value
        return value

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
        frame_num = int(self.ticks // self.ticks_between_frames)

        self.ticks += speed
        if self.ticks >= len(self.images) * self.ticks_between_frames: self.finished = True

        return self.images[frame_num], frame_num

MENU_BACKGROUND = "#1a1f2e"
MENU_OUTLINE = "#2a3b4c"
TEXT_COLOR = (180, 180, 180)
TILE_MAP = {cell_terrain.Terrain.Open: "open_tile", cell_terrain.Terrain.Forest: "forest_tile",
                    cell_terrain.Terrain.Woodcutter: "woodcutter_tile", cell_terrain.Terrain.Water: "water_tile",
                    cell_terrain.Terrain.Stone: "stone_tile", cell_terrain.Terrain.Miner: "miner_tile"}
STRUCTURE_LIST = [cell_terrain.Terrain.Miner, cell_terrain.Terrain.Woodcutter]
class Display:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.run = True
        self.delta = 0
        self.font = pygame.freetype.Font('JetBrainsMono-Regular.ttf', 18)
        self.map_cell_size = 20
        self.images = self.load_images()
        self.width, self.height = pygame.display.get_window_size()
        self.queued_animations = defaultdict(lambda: [])
        self.map = None
        self.debug_id = 0
        self.ticks = 0
        self.zoom = 0.6 * (self.width / 1200)
        self.camera_pos = [-800, 100]
        self.menu_scroll = 0

        self.text_cache = {}
        self.image_cache = LRUCache()
        self.setup_caches()

    def setup_caches(self):
        for number in "1234567890":
            surface, rect = self.font.render(number, TEXT_COLOR)
            self.text_cache[number] = (surface, rect)

    # fmt: off
    def draw_gobj(self, gobj):
        pygame.draw.circle(
            self.screen,
            gobj.color,
            gobj.pos(),
            gobj.radius)
        
    def draw_text(self, given_surface, msg, x, y, color):
        if msg.isdigit():
            surfaces = []
            width, height = 0, 0

            for number in msg:
                surface, rect = self.text_cache[number]
                surfaces.append((surface, rect))
                width += rect[2]
                height = max(height, rect[3])

            text_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            rect_x = 0
            for (surface, rect) in surfaces:
                text_surface.blit(surface, (rect_x, 0))
                rect_x += rect[2]
        else:
            if msg not in self.text_cache:
                surface, rect = self.font.render(msg, TEXT_COLOR)
                self.text_cache[msg] = (surface, None)

            text_surface = self.text_cache[msg][0]


        given_surface.blit(text_surface, (x, y))



    def draw_line(self, p1, p2, color, width=1):
        pygame.draw.line(
            self.screen,
            color,
            p1,
            p2,
            width)

    def get_tile_image(self, terrain, v, gmap):
        """
        
            Gets the terrain image based on a couple conditions
        
        """
        
        pos_to_left = vec2.Vec2(v.x - 1, v.y)
        water_to_left = v.x == 0 or gmap.cells[pos_to_left].terrain == cell_terrain.Terrain.Water

        if terrain == cell_terrain.Terrain.Water and not water_to_left:
            return self.images["water_shaded_top_tile"], "water_shaded_top_tile"

        return self.images[TILE_MAP[terrain]], TILE_MAP[terrain]

    def draw_map(self, gmap):
        for v, c in gmap.cell_render_queue:
            image = None
       
            if c.terrain not in TILE_MAP: return
            
            image, tile_name = self.get_tile_image(c.terrain, v, gmap)
 
         
            x, y = self.world_to_cord((v.x, v.y))
            self.blit(image, x, y, 50, tile_name)

            # Render animation on top of each tile
            indexes_to_remove = []
            for i, (pos, animation, animation_speed) in enumerate(self.queued_animations[(v.x, v.y)]):
                image, frame_num = animation.get_next_image(animation_speed)

                self.blit(image, pos[0], pos[1], 50, f"{animation.name}_{frame_num}")
                if animation.finished: indexes_to_remove.append(i) 

            for index in indexes_to_remove[::-1]:
                self.queued_animations[(v.x, v.y)].pop(index)

            if c.owned_by:
                self.outline_tile(v.x, v.y, self.darken(c.owned_by.color, 2), "structure")
         

            

    def draw_cities(self, cities, factions):
        for c in cities:
            f = factions[c.faction_id]
            self.outline_tile(c.pos.x, c.pos.y, f.color, "tile")

    def draw_units(self, unit_dict, factions):
        for fid, ulist in unit_dict.by_faction.items():
            fcolor = factions[fid].color
            for u in ulist:
                image = {"P": self.images["paper_unit"], "R": self.images["rock_unit"], "S": self.images["scissor_unit"]}[u.utype]
                image = image.copy()
         
                image.fill(self.darken(fcolor, 0.5), special_flags = pygame.BLEND_RGBA_MULT)

                x, y = u.display_pos

                size = 30
                if u.rank == "general": size = 50
                elif u.rank == "commander": size = 70
                size += u.additional_size

                self.blit(image, x - ((size - 30) // 2), y - ((size - 30)), size, f"{u.utype}_{fid}_{size}")



    def world_to_cord(self, pos):
        """Translates 2D array cords into cords for isometric rendering"""
        x = pos[0] * TILE_X_OFFSET - pos[1] * TILE_X_OFFSET
        y = pos[0] * TILE_Y_OFFSET + pos[1] * TILE_Y_OFFSET

        return (x, y)

    def outline_tile(self, x, y, color, type):
        image_name = {"tile": "tile_outline", "structure": "structure_outline"}[type]

        x, y = self.world_to_cord((x, y))
        outline = self.images[image_name].copy()
        
        outline.fill(color, special_flags = pygame.BLEND_MULT)
        self.blit(outline, x, y, 50, f"{image_name}_{color[0]}_{color[1]}_{color[2]}")
        

    def blit(self, image, x, y, size, name=None):
        adjusted_x = x - self.camera_pos[0]
        adjusted_y = y - self.camera_pos[1]

        adjusted_x *= self.zoom
        adjusted_y *= self.zoom       
        

        if adjusted_x > -500 and adjusted_x < self.width and adjusted_y > -500 and adjusted_y < self.height:
            if name:
                adjusted_image = self.image_cache.get((name, self.zoom))

                if adjusted_image == None:
                    adjusted_image = self.image_cache.put((name, self.zoom), pygame.transform.scale(image, (size * self.zoom, size * self.zoom)))
            else:
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

        self.screen.blit(pygame.transform.scale(self.images["turn_counter"], (200, 50)), (20, 10))

        self.draw_text(self.screen, "turn:", 30, 28, TEXT_COLOR)
        self.draw_text(self.screen, str(turn), 200 - 9 * len(str(turn)), 28, TEXT_COLOR)

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

        self.draw_rect_advanced(MENU_BACKGROUND, 200, winw - 200, 10, 190, winh - 25, (MENU_OUTLINE, 5))

        y = 25
        if sidebar_mode == "general":
            menu_surface = pygame.Surface((190, winh - 25), pygame.SRCALPHA)

            y -= self.menu_scroll
            for fid, faction in factions.items():
                if fid not in units_by_faction or (cities_by_faction[fid] == 0 and units_by_faction[fid] == 0): continue

                pygame.draw.circle(menu_surface, self.darken(faction.color, 2.5), (20, y+5), 10)
                pygame.draw.circle(menu_surface, self.darken(faction.color, 1.5), (20, y+5), 8)
                
                self.draw_text(menu_surface, faction.ID, 35, y, TEXT_COLOR)
        
                pygame.draw.line(menu_surface, self.darken(faction.color, 2.5), (20, y + 15), (20, y + 15 + 25 * 5.7), 3)

                y += 25
                
                images = ["time_clock", "unit_icon", "cities_icon", "gold_icon", "wood_icon", "stone_icon"]
                values = [faction.age, units_by_faction[fid], cities_by_faction[fid], faction.materials["gold"], faction.materials["wood"], faction.materials["stone"]]

                for i in range(len(images)):
                    image, value = images[i], values[i]
                    pygame.draw.line(menu_surface, self.darken(faction.color, 2.5), (20, y+6), (50, y+6), 3)
                    self.draw_text(menu_surface, str(value), 80, y, TEXT_COLOR)
                    menu_surface.blit(self.images[image], (60, y-2))
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

            if unit_selected.targeted_pos:
                surface, rect = self.font.render(f"Targeting: {unit_selected.targeted_pos[0]} {unit_selected.targeted_pos[1]}", TEXT_COLOR)
                menu_surface.blit(surface, (10, y))
                y += 25

            if unit_selected.general_following and unit_selected.general_following.flow_field:
                pos = (unit_selected.pos.x, unit_selected.pos.y)

                if pos in unit_selected.general_following.flow_field:
                    current_move = unit_selected.general_following.flow_field[pos]
                    surface, rect = self.font.render(f"Current move: {current_move}", TEXT_COLOR)
                    menu_surface.blit(surface, (10, y))
                    y += 25


            if unit_selected.rank == "commander":
                goal, subgoal = factions[unit_selected.faction_id].goal

                surface, rect = self.font.render(f"Goal: {goal}", TEXT_COLOR)
                menu_surface.blit(surface, (10, y))
                y += 25

                surface, rect = self.font.render(f"Subgoal: {subgoal}", TEXT_COLOR)
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
        return [max(min(int(pixel_value / strength), 255), 0) for pixel_value in color]
    
    def get_unit_actual_pos(self, unit):
        display_pos = unit.display_pos
        size = 30
        if unit.rank == "general": size = 50
        elif unit.rank == "commander": size = 70
        size += unit.additional_size

        x, y = display_pos[0] - ((size - 30) // 2), display_pos[1] - ((size - 30))

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

def gen_factions(gmap):

    factions = {}
    chosen_names = []
    while len(factions) != 7:
        name = get_faction_name(chosen_names)
        chosen_names.append(name)

        _, color = POSSIBLE_FACTIONS[len(factions)]
        factions[name] = faction.Faction(
            name, params.STARTING_FACTION_MONEY,
            ai.AI(), color, len(factions) * 999999999, name
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
        ai.AI(), color, len(factions) * 999999999, name, general
    )
    new_unit_list = []
    units_to_remove_index = []
    for i, unit in enumerate(unit_dict.by_faction[faction_id]):
        if unit.ID == general.ID or unit.general_following and unit.general_following.ID == general.ID:
            units_to_remove_index.append(i)
            new_unit_list.append(unit)
            unit.faction_id = name
            unit.move_queue = {}

    general.rank = "commander"
    if general in current_faction.generals: current_faction.generals.remove(general)
    for index in units_to_remove_index[::-1]:
        unit_dict.by_faction[faction_id].pop(index)
    general.defected_times += 1

    unit_dict.by_faction[name] = new_unit_list[:]


def RunBuildStructureCommand(cmd, gmap):
    building_pos = []

    position = vec2.Vec2(cmd.pos[0], cmd.pos[1])
    succesful_build = False

    if cmd.utype == "woodcutter" and cmd.faction.can_build_structure(params.STRUCTURE_COST["woodcutter"]) and gmap.cells[position].terrain == cell_terrain.Terrain.Forest:
        gmap.cells[position] = Cell(cell_terrain.Terrain.Woodcutter, cmd.faction)
        building_pos.append((position, cmd.utype))

        for key, val in params.STRUCTURE_COST["woodcutter"].items():
            cmd.faction.materials[key] -= val

        cmd.faction.structures.append(Structure(vec2.Vec2(cmd.pos[0], cmd.pos[1]), "woodcutter"))
        succesful_build = True

    if cmd.utype == "miner" and cmd.faction.can_build_structure(params.STRUCTURE_COST["miner"]) and gmap.cells[position].terrain == cell_terrain.Terrain.Stone:
        gmap.cells[position] = Cell(cell_terrain.Terrain.Miner, cmd.faction)
        building_pos.append((position, cmd.utype))

        
        for key, val in params.STRUCTURE_COST["miner"].items():
            cmd.faction.materials[key] -= val

        cmd.faction.structures.append(Structure(vec2.Vec2(cmd.pos[0], cmd.pos[1]), "miner"))
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
            
                # This commander had another unit die
                if other_unit.faction_id in factions and factions[other_unit.faction_id].commander:
                    factions[other_unit.faction_id].commander.soldiers_lost += 1
                
                if factions[theunit.faction_id].commander:
                    factions[theunit.faction_id].commander.soldiers_killed += 1 

            if theunit.health <= 0:
                combat_pos = theunit.pos
                theunit.dead = True
            
            if other_unit.health <= 0:
                other_unit.dead = True
        
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

def post_turn_takeovers(cities, unit_dict, factions, gmap):
    for c in cities:
        if c.pos in unit_dict.by_pos:
            unit = unit_dict.by_pos[c.pos]
            c.faction_id = unit.faction_id

    for fid, faction in factions.items():
        indexes_to_remove = []
        for i, structure in enumerate(faction.structures):
            if structure.pos in unit_dict.by_pos:
                faction_id = unit_dict.by_pos[structure.pos].faction_id
                if faction_id == fid: continue

                indexes_to_remove.append(i)

                factions[faction_id].structures.append(structure)
                gmap.cells[structure.pos].owned_by = factions[faction_id]
        
        for index in indexes_to_remove[::-1]:
            faction.structures.pop(index)



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

    flow_field_queue = []
    for city in cities:
        pos = (city.pos.x, city.pos.y)
        flow_field_queue.append(pos)

    for v, c in gmap.cell_render_queue:
        if c.terrain in (cell_terrain.Terrain.Forest, cell_terrain.Terrain.Stone):
            flow_field_queue.append((v.x, v.y))

    def run_turn(factions, gmap, cities_by_faction, unit_dict, move_cache, cities):
        commands, move_cache = Turn(factions, gmap, cities_by_faction,
                                    unit_dict.by_faction, move_cache)
        combat_positions, building_positions = RunAllCommands(commands, factions, unit_dict, cities, gmap)
        post_turn_takeovers(cities, unit_dict, factions, gmap)

        return move_cache, combat_positions, building_positions

    # Starting game speed (real time between turns) in milliseconds.
    current_turn_time_ms = 0
    speed = 512
    ticks = 0
    turn = 1
    GAME_OVER = False
    pressed_time = 0
    selected_unit = None
    dragging, hover = False, False
    desired_scroll = display.zoom
    all_stats = {}
    while display.run:
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
                    
                    speed = speed / 2
                    speed = max(speed, 16)
                elif event.key == pygame.K_RIGHT:

                    # Increase if you want a slower game speed.
                    if speed < 4096:
                        speed = speed * 2

                elif event.key == pygame.K_r:
                    return 
                    
                # elif event.key == pygame.K_u:
                #     TILE_X_OFFSET -= 1
                # elif event.key == pygame.K_i:
                #     TILE_X_OFFSET += 1
                # elif event.key == pygame.K_o:
                #     TILE_Y_OFFSET -= 1
                # elif event.key == pygame.K_p:
                #     TILE_Y_OFFSET += 1
                
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

        display.screen.fill("#121212")

        started_turn = turn
        while ticks >= speed and not GAME_OVER and turn - started_turn < 100:
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


            move_cache, combat_positions, building_positions = run_turn(factions, gmap, cities_by_faction, unit_dict, move_cache, cities)
            
            turn += 1

            game_over = CheckForGameOver(cities, unit_dict)
            if game_over[0]:
                for unit in unit_dict.by_faction[game_over[1]]:
                    if unit.rank == "general": unit.defecting = True
                # print(f"Winning faction: {game_over[1]}")
                # GAME_OVER = True


        # Move units toward their directed pos so they don't move by teleportation
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
        display.draw_ui(turn, factions, unit_dict, cities, selected_unit)
 


    
        pygame.display.flip()

        if current_turn_time_ms:
            if flow_field_queue:
                pos = flow_field_queue.pop(0)
                if pos in move_cache: continue

                move_cache[pos] = ai.create_flow_field(pos, gmap)
            

        dt = display.clock.tick(60)
        ticks += dt
        display.ticks += dt
        current_turn_time_ms = time.perf_counter()


def main(display=None):
    random.seed(None)
    winw, winh = 1400, 800

    if not display:
        display = init_display(winw, winh)

    profiler = cProfile.Profile()
    profiler.enable()

    GameLoop(display)

    profiler.disable()
    profiler.print_stats(sort='tottime')  

    main(display)


if __name__ == "__main__":
    main()
