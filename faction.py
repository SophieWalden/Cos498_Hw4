# Faction class
# You are welcome to add more data here if you want to keep
# persistent info in the faction object rather than the AI object.
# Or if you want to make the game's resources more complex.
# Currently, there's only money.

import unit, random


class Faction:
    def __init__(self, ID, money, ai, color, starting_unit_id, name, commander=None):
        self.ID = ID
        self.ai = ai
        self.next_unit_id = starting_unit_id
        self.color = color
        self.commander = commander
        self.generals = []
        self.materials = {"gold": money, "wood": 0, "stone": 0}
        self.goal = ["conquer", "fewest"]
        self.structures = []
        self.name = name
        self.age = 0

    def get_next_unit_id(self):
        uid = self.next_unit_id
        self.next_unit_id += 1
        return uid

    def can_build_unit(self, cost):
        return cost <= self.materials["gold"]
    
    def can_build_structure(self, cost):
        can_build = True

        for key, val in cost.items():
            if self.materials[key] < val:
                can_build = False
        
        return can_build
        
    # ################################################################
    def run_ai(self, factions, cities, units, gmap, move_cache):
        return self.ai.run_ai(self.ID, factions, cities, units, gmap, move_cache)

    def choose_commander(self, units):
        if not units: return None

        self.commander = random.choice(units)
        self.commander.rank = "commander"
        
    def choose_general(self, units):
        available_units = list(filter(lambda x: x.rank == "soldier", units))
        if len(available_units) == 0: return False

        chosen_general = random.choice(available_units)
        chosen_general.rank = "general"
        self.generals.append(chosen_general)

        return True
    
    def reset_generals(self):
        for general in self.generals:
            general.targeted_city = None