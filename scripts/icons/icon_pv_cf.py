"""
Generate an animated GIF of PV capacity factor (cf)
across California for a single day in 2030.
"""

from climakitae.new_core.user_interface import ClimateData

from icon_constants import WIDTH, HEIGHT, STEP
from icon_utils import make_icon_gif

print("Fetching PV capacity factor hourly data for 2030-06-15 …")
cd = ClimateData(verbosity=0)

data = (
    cd.catalog("renewable energy generation")
    .installation("pv_utility")
    .variable("cf")
    .experiment_id("ssp370")
    .source_id("EC-Earth3")
    .table_id("1hr")
    .grid_label("d03")
    .processes({"time_slice": ("2030-06-15", "2030-06-16")})
    .get()
)
print(f"Dataset retrieved: {data}")

make_icon_gif(
    data,
    out_path="pv_cf_d03_2030.gif",
    title="PV capacity factor",
    cmap="Reds",
    time_unit="h",
    vmin=0.0,
    vmax=1.0,
    width=WIDTH,
    height=HEIGHT,
    duration_ms=175,
    step=STEP,
)
