"""
Generate an animated GIF of WRF t2 (2m air temperature) at 3km (d03)
resolution across California for a single day in 2030.
"""

from climakitae.new_core.user_interface import ClimateData

from icon_constants import WIDTH, HEIGHT, STEP
from icon_utils import make_icon_gif

print("Fetching WRF t2 hourly data for 2030-06-15 at d03 …")
cd = ClimateData(verbosity=0)

data = (
    cd.catalog("cadcat")
    .activity_id("WRF")
    .institution_id("UCLA")
    .table_id("1hr")
    .grid_label("d03")
    .variable("t2")
    .processes({"time_slice": ("2030-06-15", "2030-06-16")})
    .get()
)
print(f"Dataset retrieved: {data}")

make_icon_gif(
    data,
    out_path="wrf_t2_d03_2030.gif",
    title="WRF t2 – d03",
    cmap="YlOrRd",
    time_unit="h",
    kelvin_to_celsius=True,
    width=WIDTH,
    height=HEIGHT,
    duration_ms=175,
    step=STEP,
)
