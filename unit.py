# The Unit Class
# The two areas of potential modification are:
# - The dictionaries at the top of the file
# - The roll() function.

import random
import math

# UNIT_COSTS is a constant dictionary that holds the resource (money)
# costs for each type of unit.
UNIT_COSTS = {
    "R": 100,
    "S": 100,
    "P": 100
    }

# UNIT_HEALATH is a constant dictionary that holds the starting health
# for a unit of a given unit type (utype).
UNIT_HEALTH = {
    "R": 10,
    "S": 10,
    "P": 10
    }

# UNIT_SIGHT: Not used. Ignore.
UNIT_SIGHT = {
    "R": 2,
    "S": 2,
    "P": 2
    }

# You should use this function in your AI to test unit costs
def get_unit_cost(utype):
    try:
        return UNIT_COSTS[utype]
    except KeyError:
        return math.inf

TILE_X_OFFSET = 24
TILE_Y_OFFSET = 12
class Unit:
    def __init__(self, ID, utype, faction_id, pos, health, sight_radius):

        # id: int
        self.ID = ID

        # utype: unit type
        # string: R, S or P
        self.utype = utype

        # faction_id: str
        self.faction_id = faction_id

        # pos: vec2
        self.pos = pos
        self.display_pos = self.world_to_cord(self.pos)
        self.moving = False

        # health: int
        self.health = health

        # sight_radius: int - how far it sees
        # NOT USED.
        self.sight_radius = sight_radius
        self.rank = "soldier"
        self.dead = False
        self.targeted_pos = None
        self.general_following = None
        self.additional_size = 0

        self.move_queue = {}

        self.general_accepted_death_threshhold = random.randint(5, 20)
        self.soldiers_lost, self.soldiers_killed = 0, 0
        self.defecting = False
        self.age_assigned_moves = 0
        self.targeting_age = 0

        self.aptitudes = {"gather": random.random(), "conquer": random.random() * 10, "defend": random.random()* 0.2, "gather_materials": {"wood": random.random(), "stone": random.random()}, "conquer_style": {"closest": random.random(), "fewest_enemies": random.random()}}

    def world_to_cord(self, pos):
        """Translates 2D array cords into cords for isometric rendering"""
        x = pos.x * TILE_X_OFFSET - pos.y * TILE_X_OFFSET
        y = pos.x * TILE_Y_OFFSET + pos.y * TILE_Y_OFFSET

        return [x + 10, y - 15]

    def __eq__(self, o):
        return self.ID == o.ID and self.faction_id == o.faction_id
        
    # Combat Function:
    # Essentially, it is an NxN matrix for all the different
    # unit-to-unit match ups. Currently, the winning combinations of
    # rock-paper-scissors have max damage of 20. All other
    # combinations are 10. Feel free to modify if you want.
    def roll(self, op_utype):
        if op_utype == 'R' and self.utype == 'P':
            return random.randint(0, 20)
        elif op_utype == 'P' and self.utype == 'S':
            return random.randint(0, 20)
        elif op_utype == 'S' and self.utype == 'R':
            return random.randint(0, 20)
        else:
            return random.randint(0, 10)

    def choose_targeted_city(self, citiesDict, factions, decisionType):
        available_cities = []
        units_by_faction = {}
        for fid, cities in citiesDict.items():
            if fid != self.faction_id:
                available_cities.extend(cities)

        for fid, faction in factions.items():
            units_by_faction[fid] = len(faction.generals)

        if len(available_cities) == 0: return None

        if decisionType == "closest": chosen_city = min(available_cities, key=lambda city: abs(city.pos.x - self.pos.x) + abs(city.pos.y - self.pos.y))
        else: chosen_city = min(available_cities, key=lambda city: (units_by_faction[city.faction_id], abs(city.pos.x - self.pos.x) + abs(city.pos.y - self.pos.y)))

        self.targeted_pos = (chosen_city.pos.x, chosen_city.pos.y)

    def choose_general(self, generals):
        if len(generals) == 0: return None

        chosen_general = min(generals, key=lambda general: abs(general.pos.x - self.pos.x) + abs(general.pos.y - self.pos.y))
        self.general_following = chosen_general

    def choose_target_terrain(self, gmap, terrain_types):
        minimum_distance = 9999
        terrain_found = False
        for key, cell in gmap.cells.items():
            if cell.terrain in terrain_types and (cell.owned_by == None or cell.owned_by.ID != self.faction_id):
                distance = abs(key.x - self.pos.x) + abs(key.y - self.pos.y)

                if distance < minimum_distance:
                    minimum_distance = distance
                    self.targeted_pos = (key.x, key.y)
                    terrain_found = True

        return terrain_found
    
    def choose_targeted_unit(self, units):
        available_units = []
        for fid, units_map in units.items():
            if fid != self.faction_id:
                available_units.extend(units_map)

        if len(available_units) == 0: return None

        chosen_unit = min(available_units, key=lambda unit: abs(unit.pos.x - self.pos.x) + abs(unit.pos.y - self.pos.y))
        self.targeted_pos = (chosen_unit.pos.x, chosen_unit.pos.y)

    def choose_goal(self):
        """Chooses goal based on units aptitude"""

        goal = random.choices(["gather", "conquer", "defend"], weights=[self.aptitudes["gather"], self.aptitudes["conquer"], self.aptitudes['defend']])[0]
        subgoal = None

        if goal == "gather":
            subgoal = random.choices(list(self.aptitudes["gather_materials"].keys()), weights=self.aptitudes["gather_materials"].values())[0]
        elif goal == "conquer":
            subgoal = random.choices(list(self.aptitudes["conquer_style"].keys()), weights=self.aptitudes["conquer_style"].values())[0]

        return [goal, subgoal]
        