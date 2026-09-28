import os
import sys
from pathlib import Path

os.environ["MUNSHI_OFFLINE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
