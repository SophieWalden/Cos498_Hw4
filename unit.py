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

        # health: int
        self.health = health

        # sight_radius: int - how far it sees
        # NOT USED.
        self.sight_radius = sight_radius

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
