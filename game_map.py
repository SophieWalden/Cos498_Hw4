# GameMap class
# Not much going on here. Builds the map cell by cell
# with a random terrain type.

import random
import vec2
import cell
import params
import cell_terrain

CELL_TRANSLATION_MAP = {0: cell_terrain.Terrain.Open, 1: cell_terrain.Terrain.Forest, 2: cell_terrain.Terrain.Water, 3: cell_terrain.Terrain.Stone}

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
        board = [[0 for _ in range(self.width)] for _ in range(self.height)]

        
        noise = [[random.random() for _ in range(self.width)] for _ in range(self.height)]
        stone_noise = [[random.random() for _ in range(self.width)] for _ in range(self.height)]
        
        noise = self.smooth(noise, 4)
        stone_noise = self.smooth(stone_noise, 3)
  
        for j, row in enumerate(noise):
            for i, tile in enumerate(row):
                if stone_noise[j][i] > 0.58 and tile > 0.47:
                    board[j][i] = 3
                elif tile > 0.54:
                    board[j][i] = 1
                elif tile > 0.47:
                    board[j][i] = 0
                else:
                    board[j][i] = 2
          
        
        for j, row in enumerate(board):
            for i, tile in enumerate(row):
                self.cells[vec2.Vec2(i, j)] = cell.Cell(CELL_TRANSLATION_MAP[tile])

    def smooth(self, board, depth):
        new_board = [[0] * len(board[0]) for _ in range(len(board))]

        for y, row in enumerate(board):
            for x, tile in enumerate(row):
                count = 0

                for j in range(-depth, depth + 1):
                    for i in range(-depth, depth + 1):

                        new_x, new_y = i + x, j + y
                        new_x %= len(row)
                        new_y %= len(board)
                        new_board[y][x] += board[new_y][new_x]
                        count += 1

                new_board[y][x] /= count

        return new_board

    def get_cell(self, pos):
        return self.cells[pos]
