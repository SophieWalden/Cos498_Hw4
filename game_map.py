# GameMap class
# Not much going on here. Builds the map cell by cell
# with a random terrain type.

import random
import vec2
import cell
import params
import cell_terrain

CELL_TRANSLATION_MAP = {0: cell_terrain.Terrain.Open, 1: cell_terrain.Terrain.Forest, 2: cell_terrain.Terrain.Water, 3: cell_terrain.Terrain.Stone}
FOREST_THRESHOLD = 0.54
STONE_THRESHOLD = 0.58
WATER_THREDSHOLD = 0.47

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
        forest_noise = [[random.random() for _ in range(self.width)] for _ in range(self.height)]
        
        noise = self.smooth(noise, 4)
        stone_noise = self.smooth(stone_noise, 3)
        forest_noise = self.smooth(forest_noise, 3)
  
        for j, row in enumerate(noise):
            for i, tile in enumerate(row):
                if tile <= WATER_THREDSHOLD:
                    board[j][i] = 2
                elif forest_noise[j][i] > FOREST_THRESHOLD:
                    board[j][i] = 1
                elif stone_noise[j][i] > STONE_THRESHOLD:
                    board[j][i] = 3
                else: 
                    board[j][i] = 0
            
        # Get rid of isolated water tiles
        board = self.remove_isolated(board, 2, 5)

        
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

    def remove_isolated(self, board, terrain, minimum_amount):
        """
            Performs floodfill and removes terrain if there isn't atleast minimum_amount connected
        """

        seen_nodes = set([])

        for j, row in enumerate(board):
            for i, tile in enumerate(row):

                if (i, j) not in seen_nodes and board[j][i] == terrain:
                    seen_nodes.add((i, j))
                    current_fill = [(i, j)]
                    queue = [(i, j)]

                    while queue:
                        x, y = queue.pop(0)

                        for dir_x, dir_y in [[-1, 0], [1, 0], [0, 1], [0, -1]]:
                            new_x, new_y = dir_x + x, dir_y + y
                

                            if new_x in range(len(board[0])) and new_y in range(len(board)) and board[new_y][new_x] == terrain and (new_x, new_y) not in seen_nodes:
                                seen_nodes.add((new_x, new_y))
                                queue.append((new_x, new_y))
                                current_fill.append((new_x, new_y))

                    if len(current_fill) < minimum_amount:
                        for (x, y) in current_fill:
                            board[y][x] = 0
                        



        return board

    def get_cell(self, pos):
        return self.cells[pos]
