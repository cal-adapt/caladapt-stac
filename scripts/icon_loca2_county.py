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

DATE = "2050-07-15"
WIDTH, HEIGHT = 400, 250
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

    dpi = 200
    fig, ax = plt.subplots(figsize=(WIDTH / dpi, HEIGHT / dpi), dpi=dpi)
    gdf.plot(color="#e8e8e8", ax=ax, linewidth=0.2, edgecolor="white")
    da.plot.pcolormesh(
        ax=ax, x="lon", y="lat", cmap="RdYlBu_r", add_colorbar=False, add_labels=False
    )
    gdf[gdf["county_name"] == "Los Angeles"].boundary.plot(
        ax=ax, linewidth=0.5, color="white"
    )
    ax.set_xlim(-124.4, -114.1)
    ax.set_ylim(32.5, 42.0)
    ax.set_axis_off()
    ax.set_title("")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(
        buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0, facecolor="white"
    )
    plt.close(fig)
    buf.seek(0)
    Image.open(buf).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(OUT_PATH)
    print(f"Done → {OUT_PATH}")


if __name__ == "__main__":
    main()
