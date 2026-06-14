import sys
from pathlib import Path


projekt_wurzel = Path(__file__).resolve().parents[1]
if str(projekt_wurzel) not in sys.path:
    sys.path.insert(0, str(projekt_wurzel))
