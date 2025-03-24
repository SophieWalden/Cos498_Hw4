# Terrain Enum
# If you want to add more terrain types, start here.
#
# Next jump to the params.py and game_map.py file to see how maps
# are generated.

import enum

class Terrain(enum.Enum):
    Open = 0
    Forest = 1
