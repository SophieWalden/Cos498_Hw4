# Cell Class
# Stores the attack/defense modifiers and the color
# for each terrain type. Terrain types are defined in
# cell_terrain.py
#
# Currently, Open terrain gives a +2 for an attacker and
# nothing to a defender. Forest gives a +2 to the defender
# and nothing to the attacker.
#
# Feel free to modify.


import cell_terrain


ATTACK_DICT = {
    cell_terrain.Terrain.Open: 2,
    cell_terrain.Terrain.Forest: 0,
    cell_terrain.Terrain.Woodcutter: 0
}

DEFENSE_DICT = {
    cell_terrain.Terrain.Open: 0,
    cell_terrain.Terrain.Forest: 2,
    cell_terrain.Terrain.Woodcutter: 2
}

class Cell:
    def __init__(self, terrain):
        self.terrain = terrain

    
    def get_attack_mod(self):
        return ATTACK_DICT[self.terrain]

    def get_defense_mod(self):
        return DEFENSE_DICT[self.terrain]
