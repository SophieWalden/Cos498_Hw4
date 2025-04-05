import cell_terrain
import random

# ##########################################################33
# MAP RELATED STUFF

# Relative probabilities for each terrain type to appear on
# the map. Currently, Open terrain is four times more likely to
# appear than forest. The values are relative (discrete distribution).
# For example, 5 and 20 would produce the same map as the values
# below. If you add more terrain types, adding them here
# will cause them to appear on the map. Terrain generation
# is completely random. There's no fancy procedural content gen.
# algorithms here. If you want something fancier, you'd need
# to add them below and call them in game_map.py.



MODE = "nature" # versus or nature determines whether defecting is allowed
    
# ##########################################################33
# FACTION STUFF
#
# How much money does a city generate per turn?
CITY_INCOME = 3

# How many starting factions in the game?
if MODE == "nature":
    FACTIONS_COUNT = 2
    CITIES_PER_FACTION = 6
elif MODE == "versus":
    FACTIONS_COUNT = 2
    CITIES_PER_FACTION = 6

# How much money does a faction start with?
STARTING_FACTION_MONEY = 500

# How much money do structures cost?
STRUCTURE_COST = {
    "woodcutter": {"gold": 250},
    "miner": {"gold": 50, "wood": 30}
}

# What do structures give every turn?
STRUCTURE_OUTPUT = {
    "woodcutter": {"wood": 1},
    "miner": {"stone": 1}
}

# The rest of this is used to give the cities random
# ID (aka names). These random names don't appear visibly
# in the game, but if you want them to, they are there
# and already being loaded into the cities on instantiation.
CITY_IDS = []
with open('city_names') as f:
    for line in f:
        line = line.strip()
        CITY_IDS.append(line)
        
FACTION_NAMES = []
with open('faction_names.txt') as f:
    for line in f:
        line = line.strip()
        if line: FACTION_NAMES.append(line)

def get_random_city_ID():
    return random.choice(CITY_IDS)
