"""
Generate an animated GIF of LOCA2 t2 (2m air temperature)
across California for a single month in 2030.
"""

from climakitae.new_core.user_interface import ClimateData

from icon_utils import make_icon_gif

print("Fetching LOCA2 t2 daily data for 2030-06 …")
cd = ClimateData(verbosity=0)

data = (
    cd.catalog("cadcat")
    .activity_id("LOCA2")
    .variable("t2")
    .experiment_id("ssp370")
    .source_id("CESM2")
    .grid_label("d03")
    .table_id("day")
    .processes({"time_slice": ("2030-06-01", "2030-06-30")})
    .get()
)
print(f"Dataset retrieved: {data}")

make_icon_gif(
    data,
    out_path="loca2_t2_2030.gif",
    title="LOCA2 t2 – daily\n{timestamp}",
    cmap="RdYlBu_r",
    unit_label="Temperature (°C)",
    time_unit="D",
    kelvin_to_celsius=True,
    width=400,
    height=250,
)
