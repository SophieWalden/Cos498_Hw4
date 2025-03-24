import vec2

class Command:
    def __init__(self, faction_id):
        self.faction_id = faction_id

class MoveUnitCommand(Command):
    def __init__(self, faction_id, unit_id, direction):
        Command.__init__(self, faction_id)
        self.unit_id = unit_id
        self.direction = direction       

class BuildUnitCommand(Command):
    def __init__(self, faction_id, city_id, utype):
        Command.__init__(self, faction_id)
        self.city_id = city_id
        self.utype = utype

