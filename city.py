# City Class
# Not much to edit here unless you are making the resource
# aspect of the game more complicated.

import unit


class City:
    def __init__(self, ID, pos, faction_id, income):

        # ID: str - identifier for the city
        self.ID = ID

        # pos: Vec2 - x,y location of the city on the map
        self.pos = pos

        # faction_id: str - ID of the faction that owns the city
        self.faction_id = faction_id

        # income: int - how much money the city generates.
        self.income = income

    def generate_income(self):
        return self.income

    def build_unit(self, ID, utype):
        return unit.Unit(ID, utype, self.faction_id, self.pos)

    def conqueror(self, faction_id):
        self.faction_id = faction_id
