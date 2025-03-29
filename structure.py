import params

class Structure:
    def __init__(self, pos, type):
        self.pos, self.type = pos, type

    def generate_material(self):
        return params.STRUCTURE_OUTPUT[self.type]