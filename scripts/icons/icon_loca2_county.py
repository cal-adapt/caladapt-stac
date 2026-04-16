"""icon_loca2_county.py

Generate a static choropleth PNG icon of LOCA2 county-level tasmax across California.

Usage (run in climakitae environment):
    python icon_loca2_county.py
"""

import io
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import s3fs
import xarray as xr
import geopandas as gpd
from PIL import Image

from icon_constants import WIDTH, HEIGHT, DPI, title_kwargs

SCALE = 5

DATE = "2050-07-15"
OUT_PATH = "loca2_county_icon.png"


def main():
    fs = s3fs.S3FileSystem(anon=True)

    print("Loading county geometries...")
    gdf = gpd.read_file(
        "https://cadcat.s3.amazonaws.com/geometries/ca-counties-geometries.geojson"
    )

    print("Reading LA county data...")
    with fs.open(
        "cadcat/loca2/ucb/netcdf/county/day/06037_tasmax_day_TaiESM1_ssp370_r1i1p1f1.nc"
    ) as f:
        ds = xr.open_dataset(f)
        da = ds["tasmax"].sel(time=DATE, method="nearest")
        da = da - 273.15 if float(da.mean()) > 100 else da

    dpi = DPI
    fig, ax = plt.subplots(figsize=(WIDTH * SCALE / dpi, HEIGHT * SCALE / dpi), dpi=dpi)
    gdf.plot(color="#e8e8e8", ax=ax, linewidth=0, edgecolor="none")
    da.plot.pcolormesh(
        ax=ax, x="lon", y="lat", cmap="YlOrRd", add_colorbar=False, add_labels=False
    )
    gdf.boundary.plot(ax=ax, linewidth=1.5, color="#888888", zorder=3)

    n_counties = len(gdf)
    ax.text(
        0.97, 0.95,
        f"{n_counties} CA counties",
        transform=ax.transAxes,
        zorder=5,
        **title_kwargs(SCALE),
    )

    ax.set_xlim(-124.4, -114.1)
    ax.set_ylim(32.5, 42.0)
    ax.set_aspect("auto")
    ax.set_axis_off()
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    Image.open(buf).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(OUT_PATH)
    print(f"Done → {OUT_PATH}")


if __name__ == "__main__":
    main()
