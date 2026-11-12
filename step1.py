from pymgrid import Microgrid

mg = Microgrid.from_scenario(microgrid_number=0)

print(mg)                      # what modules exist?
print(mg.modules.keys())       # their names
print(mg.state_series.head())  # the numbers the controller sees
