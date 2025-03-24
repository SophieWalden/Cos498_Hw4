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
CELL_TERRAIN_PROBABILITY = {
    cell_terrain.Terrain.Forest: 1,
    cell_terrain.Terrain.Open: 4
    }

TERRAINS = list(CELL_TERRAIN_PROBABILITY.keys())
PROBS = list(CELL_TERRAIN_PROBABILITY.values())
TOTAL = sum(PROBS)

running_sum = 0
for i, p in enumerate(PROBS):
    PROBS[i] = (p+running_sum)/TOTAL
    running_sum += p
    
def get_random_terrain(roll):
    for i, p in enumerate(PROBS):
        if roll <= p:
            return TERRAINS[i]
    #print(roll)
    
# ##########################################################33
# FACTION STUFF
#
# How much money does a city generate per turn?
CITY_INCOME = 10

# How many cities does each faction start with?
CITIES_PER_FACTION = 5

# How much money does a faction start with?
STARTING_FACTION_MONEY = 1000

# The rest of this is used to give the cities random
# ID (aka names). These random names don't appear visibly
# in the game, but if you want them to, they are there
# and already being loaded into the cities on instantiation.
CITY_IDS = []
with open('city_names') as f:
    for line in f:
        line = line.strip()
        CITY_IDS.append(line)

def get_random_city_ID():
    return random.choice(CITY_IDS)
