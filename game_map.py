# GameMap class
# Not much going on here. Builds the map cell by cell
# with a random terrain type.

import random
import vec2
import cell
import params
import cell_terrain

CELL_TRANSLATION_MAP = {0: cell_terrain.Terrain.Open, 1: cell_terrain.Terrain.Forest}

class GameMap:
    def __init__(self, width, height):
        self.height = height
        self.width = width
        self.cells = {}
        
        self.gen_board()
        self.cell_render_queue = sorted(self.cells.items(), key=lambda x: x[0].x + x[0].y)
    
    def rerender(self):
        self.cell_render_queue = sorted(self.cells.items(), key=lambda x: x[0].x + x[0].y)

    def gen_board(self):
        noise = [[0 for _ in range(self.width)] for _ in range(self.height)]
        board = [[0 for _ in range(self.width)] for _ in range(self.height)]
        for j, row in enumerate(noise):
            for i, tile in enumerate(row):
                noise[j][i] = random.randint(0, 10)

        for j, row in enumerate(noise):
            for i, tile in enumerate(row):
                tile_sum = 0

                for direction in [[-1, 0], [1, 0], [0, 1], [0, -1], [-1, -1], [1, 1], [1, -1], [-1, 1], [0, 0]]:
                    x, y = i + direction[0], j + direction[1]
                    x %= len(noise[0])
                    y %= len(noise)

                    tile_sum += noise[y][x]
                
                board[j][i] = int(tile_sum > 50)
        
        for j, row in enumerate(board):
            for i, tile in enumerate(row):
                self.cells[vec2.Vec2(i, j)] = cell.Cell(CELL_TRANSLATION_MAP[tile])

    def get_cell(self, pos):
        return self.cells[pos]
