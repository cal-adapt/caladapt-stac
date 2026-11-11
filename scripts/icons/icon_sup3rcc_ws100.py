"""
Generate an animated GIF of Sup3rCC 100 m wind speed (ws100)
across California for a single day in 2030.

Sup3rCC isn't in the climakitae catalog, so this opens the zarr store directly.
The store is chunked 2621 hours x 100 x 100 cells, so the read is cropped to
California to avoid pulling the whole CONUS grid.
"""

import xarray as xr

from icon_constants import WIDTH, HEIGHT
from icon_utils import make_icon_gif

STORE = "s3://cadcat/sup3r/nlr/ec-earth3-cc/ssp245/1hr/ws100/conus4km/"
CA_BOUNDS = (-124.5, 32.5, -114.0, 42.1)  # west, south, east, north

print("Fetching Sup3rCC 100 m wind speed hourly data for 2030-06-15 …")
ds = xr.open_zarr(STORE, storage_options={"anon": True})
west, south, east, north = CA_BOUNDS
lat_slice = slice(south, north) if ds.lat[0] < ds.lat[-1] else slice(north, south)
data = ds["ws100"].sel(
    time=slice("2030-06-15", "2030-06-16T00"),
    lat=lat_slice,
    lon=slice(west, east),
)
print(f"Data selected: {data.sizes}")

make_icon_gif(
    data,
    out_path="sup3rcc_ws100_2030.gif",
    title="Wind speed at 100 m",
    cmap="Blues",
    time_unit="h",
    vmin=0.0,
    vmax=20.0,
    width=WIDTH,
    height=HEIGHT,
    # Every 4th hour: the 4 km detail makes each frame ~390 KB, so 24 frames
    # would be ~9 MB.
    duration_ms=600,
    step=4,
)
