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


class Display:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.run = True
        self.delta = 0
        self.font = None
        self.map_cell_size = 20
        self.images = self.load_images()
        self.zoom = 1
        self.camera_pos = [0, 0]
        self.width, self.height = pygame.display.get_window_size()

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
        for v, c in sorted(gmap.cells.items(), key = lambda x: x[0].x + x[0].y):
            
            image = None

            if c.terrain == cell_terrain.Terrain.Open:
                image = self.images["open_tile"]
            else: 
                image = self.images["forest_tile"]

            x, y = self.world_to_cord((v.x, v.y))
            self.blit(image, x, y, 50)

            

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

                x, y = self.world_to_cord([u.pos.x, u.pos.y])
                y-= 15
                x += 10

                self.blit(image, x, y, 30)

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
            
    def load_images(self):
        images = {}
        for filename in os.listdir("images"):
            full_path = f"images/{filename}"
            key = filename[:filename.index(".")]

            images[key] = pygame.image.load(full_path).convert_alpha()

        return images


def init_display(sw, sh):
    pygame.init()
    screen = pygame.display.set_mode((sw, sh), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    display = Display(screen, clock)
    display.font = pygame.freetype.Font('JuliaMono-Bold.ttf', 18)
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


def gen_factions(gmap):

    factions = {}
    factions['Red'] = faction.Faction(
        'Red', params.STARTING_FACTION_MONEY,
        ai.AI(), (255, 0, 0))
    factions['Blue'] = faction.Faction(
        'Blue', params.STARTING_FACTION_MONEY,
        ai.AI(), (0, 0, 255))
    factions['Green'] = faction.Faction(
        'Green', params.STARTING_FACTION_MONEY,
        ai.AI(), (0, 255, 0))
    factions['Yellow'] = faction.Faction(
        'Yellow', params.STARTING_FACTION_MONEY,
        ai.AI(), (255, 255, 0))

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
            if new_city_pos not in city_positions:
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
def Turn(factions, gmap, cities_by_faction, units_by_faction):

    commands = []

    for fid, f in factions.items():

        cmds = f.run_ai(factions, cities_by_faction, units_by_faction, gmap)
        commands += cmds

    return commands

# RunAllCommands:
# Executes all commands from the current turn.
# Shuffles the commands to reduce P1 bias (maybe).
# Basically this is just a dispatch function.
def RunAllCommands(commands, factions, unit_dict, cities, gmap):
    random.shuffle(commands)
    move_list = []
    for cmd in commands:
        if isinstance(cmd, command.MoveUnitCommand):
            RunMoveCommand(cmd, factions, unit_dict, cities, gmap, move_list)
        elif isinstance(cmd, command.BuildUnitCommand):
            RunBuildCommand(cmd, factions, unit_dict, cities, gmap)
        else:
            print(f"Bad command type: {type(cmd)}")

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
    move_successful = False
    if unit_dict.is_pos_free(new_pos):
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
                old_pos = theunit.pos
                theunit.pos = new_pos
                unit_dict.move_unit(u, old_pos, new_pos)
                move_successful = True
        
    # Check if the move conquerored a city
    if move_successful:
        for c in cities:
            if new_pos == c.pos:
                c.faction_id = u.faction_id
                break

# RunBuildCommand:
# Executes the BuildUnitCommand.
def RunBuildCommand(cmd, factions, unit_dict, cities, gmap):
    # How much does the unit cost?
    f = factions[cmd.faction_id]
    cost = unit.get_unit_cost(cmd.utype)

    # Does the faction have the available resources (money)?
    if f.can_build_unit(cost):

        # Look for the city
        for c in cities:
            if c.ID == cmd.city_id:

                # If there's no unit in the city, build.
                # Add to the unit dictionary and charge
                # the faction for its purchase.
                if unit_dict.is_pos_free(c.pos):

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


def CheckForGameOver(cities):
    faction_ids_with_cities = []
    for c in cities:
        if c.faction_id not in faction_ids_with_cities:
            faction_ids_with_cities.append(c.faction_id)
    return len(faction_ids_with_cities) == 1, faction_ids_with_cities[0]
        
    
# ###########################################################3
# GAME LOOP
# Where the magic happens.
# I've marked below where you might want to edit things
# for different reasons.
# ###########################################################

def handle_mouse_functions(offset):
    rel, pressed = pygame.mouse.get_rel(), pygame.mouse.get_pressed()

    if pressed[0]:
        offset[0] += -rel[0]
        offset[1] += -rel[1]



def GameLoop(display):
    global TILE_X_OFFSET, TILE_Y_OFFSET
    
    winw, winh = pygame.display.get_window_size()

    # Width and Height (in cells) of the game map. If you want
    # a bigger/smaller map you will need to coordinate these values
    # with two other things.
    # - The window size below in main().
    # - The map_cell_size given in the Display class above.
    gmap = gen_game_map(60, 60)
    
    factions = gen_factions(gmap)
    cities = gen_cities(gmap, list(factions.keys()))
    unit_dict = UnitDict(list(factions.keys()))


    # Starting game speed (real time between turns) in milliseconds.
    speed = 1024
    ticks = 0
    turn = 1
    while display.run:
        dt = display.clock.tick(60)
        ticks += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                display.run = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    display.run = False
                elif event.key == pygame.K_LEFT:

                    # Lower if you want a faster game speed.
                    if speed > 1:
                        speed = speed // 2
                elif event.key == pygame.K_RIGHT:

                    # Increase if you want a slower game speed.
                    if speed < 4096:
                        speed = speed * 2
                elif event.key == pygame.K_u:
                    TILE_Y_OFFSET -= 1
                elif event.key == pygame.K_i:
                    TILE_Y_OFFSET += 1
                elif event.key == pygame.K_o:
                    TILE_X_OFFSET -= 1
                elif event.key == pygame.K_p:
                    TILE_X_OFFSET += 1
            elif event.type == pygame.MOUSEWHEEL:

                scroll_val = min(max(event.y, -3), 3)/6 + 1
                display.zoom *= scroll_val
                display.zoom = max(min(display.zoom, 10), 0.1)

            elif event.type == pygame.VIDEORESIZE:
                display.width, display.height = event.w, event.h
                display.screen = pygame.display.set_mode((event.w, event.h),
                                              pygame.RESIZABLE)

        
        handle_mouse_functions(display.camera_pos)

        display.screen.fill("black")

        if ticks >= speed:
            ticks = 0
            cities_by_faction = {}
            for fid, f in factions.items():
                faction_cities = FactionPreTurn(cities, f)
                cities_by_faction[fid] = faction_cities

            commands = Turn(factions, gmap,
                            cities_by_faction,
                            unit_dict.by_faction)
            RunAllCommands(commands, factions, unit_dict, cities, gmap)
            turn += 1

            game_over = CheckForGameOver(cities)
            if game_over[0]:
                print(f"Winning faction: {game_over[1]}")
                display.run = False
            

        display.draw_map(gmap)
        display.draw_cities(cities, factions)
        display.draw_units(unit_dict, factions)

        # ###########################################3
        # RIGHT_SIDE UI
        # pygame.draw.rect(display.screen, (100, 100, 100), (winw - 200, 0, 200, winh))

        # display.draw_text(f"TURN {turn}", 1205, 5, "black")
        # display.draw_text(f"{'Fctn':<5} {'C':>2} {'U':>3} {'M':>4}",
        #                   1205, 25, "black")
        # y = 45
        # for fid, f in factions.items():
        #     num_cities = 0
        #     for c in cities:
        #         if c.faction_id == fid:
        #             num_cities += 1
        #     display.draw_text(f"{fid:<5} {num_cities:>2} {len(unit_dict.by_faction[fid]):>3} {f.money:>4}",
        #                       1205, y, "black")
        #     y += 20

        # display.draw_text(f"SPEED {speed}", 1205, 305, "black")


        pygame.display.flip()


def main():
    random.seed(None)
    display = init_display(1400, 800)
    GameLoop(display)


if __name__ == "__main__":
    main()
