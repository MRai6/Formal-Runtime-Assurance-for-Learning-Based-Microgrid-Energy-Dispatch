import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load .env file from project root or current working directory
_ROOT_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _ROOT_DIR / ".env"

if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)
else:
    load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Battery Specifications & Safety Constraints
BATTERY_KWH = 100.0      # battery capacity (kWh)
SOC_MIN = 0.20           # 20% minimum safe state of charge
SOC_MAX = 0.90           # 90% maximum safe state of charge
MAX_POWER_KW = 50.0      # max charge/discharge power rate (kW)
DT_HOURS = 1.0           # discrete simulation time step (1 hour)
SEED = 42                # base random seed
