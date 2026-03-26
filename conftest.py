import sys
import os

_base = os.path.dirname(__file__)

# src/ — for top-level packages (db, routers, util, constants, …)
sys.path.insert(0, os.path.join(_base, "src"))

# src/app/ — app/main.py does `from middleware import …` which lives here
sys.path.insert(0, os.path.join(_base, "src", "app"))
