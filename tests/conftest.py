import os
import sys

PROJECT_ROOT = "/home/nishy/Desktop/automatizacion broker"
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
