import os
import sys
from pathlib import Path

os.environ.setdefault("PAKKA_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
