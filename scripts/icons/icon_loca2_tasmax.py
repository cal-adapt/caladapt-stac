"""
Generate an animated GIF of LOCA2 tasmax (daily max temperature)
across California for a single month in 2030.
"""

from climakitae.new_core.user_interface import ClimateData

from icon_constants import WIDTH, HEIGHT, STEP
from icon_utils import make_icon_gif

print("Fetching LOCA2 tasmax EC-Earth3 daily data for 2030-06 …")
cd = ClimateData(verbosity=0)

data = (
    cd.catalog("cadcat")
    .activity_id("LOCA2")
    .variable("tasmax")
    .experiment_id("ssp370")
    .source_id("EC-Earth3")
    .grid_label("d03")
    .table_id("day")
    .processes({"time_slice": ("2030-06-01", "2030-06-30")})
    .get()
)
print(f"Dataset retrieved: {data}")

make_icon_gif(
    data,
    out_path="loca2_tasmax_2030.gif",
    title="LOCA2 tasmax",
    cmap="YlOrRd",
    time_unit="D",
    kelvin_to_celsius=True,
    width=WIDTH,
    height=HEIGHT,
    duration_ms=175,
    step=STEP,
)
