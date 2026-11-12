import os
from pathlib import Path
import numpy as np
import pandas as pd
from config import SEED

HERE = Path(__file__).resolve().parent
output_path = HERE / "microgrid_data.csv"

rng = np.random.default_rng(SEED)
t = pd.date_range("2025-01-01", periods=8760, freq="h")
hour = t.hour.values

# solar: bell curve 6am-6pm, scaled by random cloudiness per day
daylight = np.clip(np.sin((hour - 6) / 12 * np.pi), 0, None)
cloud = np.repeat(rng.uniform(0.3, 1.0, 365), 24)
solar = 80 * daylight * cloud

# load: base + morning and evening peaks + noise
load = (30 + 15*np.exp(-((hour-8)**2)/8) + 30*np.exp(-((hour-19)**2)/6)
        + rng.normal(0, 3, 8760)).clip(10)

# price (Rs/kWh): cheap night, medium day, expensive evening peak
price = np.where((hour >= 18) & (hour <= 22), 9.0,
        np.where((hour >= 6) & (hour < 18), 6.0, 4.0))

pd.DataFrame({"timestamp": t, "solar_kw": solar.round(2),
              "load_kw": load.round(2), "price_inr_kwh": price}
             ).to_csv(output_path, index=False)
print(f"done: generated {len(t)} records at {output_path}")
