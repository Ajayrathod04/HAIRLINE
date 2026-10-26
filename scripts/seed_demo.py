"""Create simulated demo cases (all flagged SIMULATED) in the configured store. Same as HL_SEED_DEMO=1 on boot."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hairline.config import Config
from hairline.server import create_app

cfg = Config.from_env()
cfg.seed_demo = True
create_app(cfg)
print("seeded (only when the store had no cases)")
