import pygame, params, time, os, vec2
from collections import OrderedDict, defaultdict
import cell_terrain

TILE_X_OFFSET = 24
TILE_Y_OFFSET = 12
IMAGE_SIZE = 50
MODE = params.MODE

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

        self.show_dropdown, self.dropdown_click_cooldown = False, False

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

            width += 2 * len(surfaces)
            text_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            rect_x = 0
            for (surface, rect) in surfaces:
                text_surface.blit(surface, (rect_x, 0))
                rect_x += rect[2] + 2
        else:
            if msg not in self.text_cache:
                surface, rect = self.font.render(msg, color)
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
        
        if terrain == cell_terrain.Terrain.Water and (v.x == 0 or gmap.cells[vec2.Vec2(v.x - 1, v.y)].terrain != cell_terrain.Terrain.Water):
            return self.images["water_shaded_top_tile"], "water_shaded_top_tile"

        return self.images[TILE_MAP[terrain]], TILE_MAP[terrain]

    def draw_map(self, gmap):
        for v, c in gmap.cell_render_queue:
            if self.is_onscreen(v.x, v.y, 50):
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
                size = 30
                if u.rank == "general": size = 50
                elif u.rank == "commander": size = 70
                size += u.additional_size

                x, y = u.display_pos
                if not self.is_onscreen(x, y, size, False): continue

                image = {"P": self.images["paper_unit"], "R": self.images["rock_unit"], "S": self.images["scissor_unit"]}[u.utype]
                image = image.copy()
         
                image.fill(self.darken(fcolor, 0.5), special_flags = pygame.BLEND_RGBA_MULT)

                self.blit(image, x - ((size - 30) // 2), y - ((size - 30)), size, f"{u.utype}_{fcolor[0]}_{fcolor[1]}_{fcolor[2]}_{size}")



    def world_to_cord(self, pos):
        """Translates 2D array cords into cords for isometric rendering"""
        x = pos[0] * TILE_X_OFFSET - pos[1] * TILE_X_OFFSET
        y = pos[0] * TILE_Y_OFFSET + pos[1] * TILE_Y_OFFSET

        return (x, y)

    def outline_tile(self, x, y, color, type):
        if not self.is_onscreen(x, y, 50): return

        image_name = {"tile": "tile_outline", "structure": "structure_outline"}[type]

        x, y = self.world_to_cord((x, y))
        outline = self.images[image_name].copy()
        
        outline.fill(color, special_flags = pygame.BLEND_MULT)
        self.blit(outline, x, y, 50, f"{image_name}_{color[0]}_{color[1]}_{color[2]}")
        
    
    def is_onscreen(self, x, y, size, cord_adjustment=True):
        if cord_adjustment: x,y = x * TILE_X_OFFSET - y * TILE_X_OFFSET, x * TILE_Y_OFFSET + y * TILE_Y_OFFSET
        
        adjusted_x = x - self.camera_pos[0]
        adjusted_y = y - self.camera_pos[1]

        adjusted_x *= self.zoom
        adjusted_y *= self.zoom

        return adjusted_x > -size * self.zoom and adjusted_x < self.width and adjusted_y > -size * self.zoom and adjusted_y < self.height

    def blit(self, image, x, y, size, name=None):
        adjusted_x = x - self.camera_pos[0]
        adjusted_y = y - self.camera_pos[1]

        adjusted_x *= self.zoom
        adjusted_y *= self.zoom       
        

        if adjusted_x > -size * self.zoom and adjusted_x < self.width and adjusted_y > -size * self.zoom and adjusted_y < self.height:
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
    
    def clear(self):
        self.queued_animations = defaultdict(lambda: [])
    
    def draw_ui(self, turn, factions, units, cities, speed, unit_selected=None):

        winw, winh = pygame.display.get_window_size()

        self.screen.blit(pygame.transform.scale(self.images["turn_counter"], (200, 50)), (20, 10))

        self.draw_text(self.screen, "turn:", 30, 28, TEXT_COLOR)
        self.draw_text(self.screen, str(turn), 200 - 9 * len(str(turn)), 28, TEXT_COLOR)

        faction_colors = {key: value.color for key, value in factions.items()}
        units_by_faction = {key: len(value) for key, value in units.by_faction.items()}

        cities_by_faction = {key: sum(city.faction_id == value.ID for city in cities) for key, value in factions.items()}
        cities_sum = len(cities)



        width = (winw - 400) - 270
        if cities_sum > 0:
            cities_normalized = {key: value/cities_sum for key, value in cities_by_faction.items()}

            x = 240
            for i, (key, value) in enumerate(cities_normalized.items()):
                color = faction_colors[key]

                self.draw_rect_advanced(self.darken(color, 1.5), 200,x, 10, int(value * width), 10, (self.darken(color, 3), 2))
                x += int(value * width)
        else:
            pygame.draw.rect(self.screen, (100, 100, 100), (200, 10, width, 5))


        # Dropdown mode selector
        pos, pressed = pygame.mouse.get_pos(), pygame.mouse.get_pressed()
        dropdown_hovering = pos[0] > winw - 410 and pos[0] < (winw - 410) + 200 and pos[1] < 40 and pos[1] > 10
        self.draw_rect_advanced((150, 150, 150) if not dropdown_hovering else (125, 125, 125), 200, winw - 410, 10, 200, 30, ((75, 75, 75), 5))
        self.draw_text(self.screen, params.MODE, winw - 400, 20, (0, 0, 0))
        pygame.draw.polygon(self.screen, (20, 20, 20), [(winw - 235, 18), (winw - 220, 18), (winw - 227, 32)])

        if self.show_dropdown:
            display_index = 0
            for mode in ["evolution", "versus", "endless"]:
                if mode != params.MODE:
                    display_index += 1
                    selection_hovering = pos[0] > winw - 410 and pos[0] < (winw - 410) + 200 and pos[1] < 40 + display_index * 30 and pos[1] > 10 + display_index * 30
                    self.draw_rect_advanced((150, 150, 150) if not selection_hovering else (125, 125, 125), 200, winw - 410, 10 + display_index * 30, 200, 30, ((75, 75, 75), 5))
                    self.draw_text(self.screen, mode, winw - 400, 18 + display_index * 30, (0, 0, 0))

                    if selection_hovering and pressed[0]:
                        params.MODE = mode
                        return "reset", speed


        if dropdown_hovering and pressed[0] and not self.show_dropdown and not self.dropdown_click_cooldown: 
            self.show_dropdown = True
            self.dropdown_click_cooldown = True
        if pressed[0] and not self.dropdown_click_cooldown and self.show_dropdown: 
            self.dropdown_click_cooldown = True
            self.show_dropdown = False

        if not pressed[0]: self.dropdown_click_cooldown = False

        # Unit sidebar
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
            if unit_selected.faction_id in factions:

                self.draw_text(menu_surface, "Pos:", 10, y, TEXT_COLOR)
                self.draw_text(menu_surface, str(unit_selected.pos.x), 60, y, TEXT_COLOR)
                self.draw_text(menu_surface, str(unit_selected.pos.y), 70 + 9 * len(str(unit_selected.pos.x)), y, TEXT_COLOR)

                y += 25

                self.draw_text(menu_surface, "Type:", 10, y, TEXT_COLOR)
                self.draw_text(menu_surface, str(unit_selected.utype), 70, y, TEXT_COLOR)
                y += 25
           
                self.draw_text(menu_surface, "Rank:", 10, y, TEXT_COLOR)
                self.draw_text(menu_surface, str(unit_selected.rank), 70, y, TEXT_COLOR)
                y += 25

                self.draw_text(menu_surface, "Health:", 10, y, TEXT_COLOR)
                self.draw_text(menu_surface, str(unit_selected.health), 90, y, TEXT_COLOR)
                y += 25

                self.draw_text(menu_surface, "Damage:", 10, y, TEXT_COLOR)
                self.draw_text(menu_surface, str(unit_selected.damage_buff + 10), 90, y, TEXT_COLOR)
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

        return None, speed

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
