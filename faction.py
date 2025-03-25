# Faction class
# You are welcome to add more data here if you want to keep
# persistent info in the faction object rather than the AI object.
# Or if you want to make the game's resources more complex.
# Currently, there's only money.

import unit, random


class Faction:
    def __init__(self, ID, money, ai, color, starting_unit_id):
        self.ID = ID
        self.money = money
        self.ai = ai
        self.next_unit_id = starting_unit_id
        self.color = color
        self.commander = None
        self.generals = []
        self.goal = ["conquer", "cities"]

    def get_next_unit_id(self):
        uid = self.next_unit_id
        self.next_unit_id += 1
        return uid

    def can_build_unit(self, cost):
        return cost <= self.money
        
    # ################################################################
    def run_ai(self, factions, cities, units, gmap):
        return self.ai.run_ai(self.ID, factions, cities, units, gmap)

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