"""
Generate a static PNG icon showing HDP weather station locations across the WECC region,
colored by network.
"""

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
from PIL import Image

from icon_constants import WIDTH, HEIGHT, DPI, OCEAN_COLOR, LAND_COLOR, COUNTRY_EDGE_COLOR, STATE_EDGE_COLOR, title_kwargs

OUT_PATH = "hdp_icon.png"
WECC_BOUNDS = (-125.0, 25.0, -100.0, 52.0)

HDP_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/hdp-station-coords.geojson"
)
STATES_URL = "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces.zip"
COUNTRIES_URL = "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip"


def main():
    print("Loading station coords...")
    stations = gpd.read_file(HDP_STATION_COORDS_URL)

    print("Loading boundaries...")
    states = gpd.read_file(STATES_URL)
    states = states.cx[WECC_BOUNDS[0]:WECC_BOUNDS[2], WECC_BOUNDS[1]:WECC_BOUNDS[3]]
    countries = gpd.read_file(COUNTRIES_URL)
    countries = countries.cx[WECC_BOUNDS[0]:WECC_BOUNDS[2], WECC_BOUNDS[1]:WECC_BOUNDS[3]]

    # Assign a color to each network
    networks = sorted(stations["network"].unique())
    palette = (
        list(plt.cm.tab20.colors) +
        list(plt.cm.tab20b.colors) +
        list(plt.cm.tab20c.colors)
    )
    network_color = {net: palette[i % len(palette)] for i, net in enumerate(networks)}
    colors = [network_color[n] for n in stations["network"]]

    scale = 2
    dpi = DPI
    fig, ax = plt.subplots(figsize=(WIDTH * scale / dpi, HEIGHT * scale / dpi), dpi=dpi)
    fig.set_facecolor(OCEAN_COLOR)
    ax.set_facecolor(OCEAN_COLOR)

    countries.plot(ax=ax, color=LAND_COLOR, edgecolor=COUNTRY_EDGE_COLOR, linewidth=1.2, zorder=1)
    states.plot(ax=ax, color=LAND_COLOR, edgecolor=STATE_EDGE_COLOR, linewidth=0.6, zorder=2)
    ax.scatter(
        stations.geometry.x,
        stations.geometry.y,
        c=colors,
        s=20,
        alpha=0.75,
        zorder=3,
        linewidths=0,
    )

    n_networks = len(networks)
    n_stations = len(stations)
    ax.text(
        0.97, 0.95,
        f"{n_networks} networks · {n_stations:,} stations",
        transform=ax.transAxes,
        **title_kwargs(scale=2),
        zorder=5,
    )

    ax.set_xlim(WECC_BOUNDS[0], WECC_BOUNDS[2])
    ax.set_ylim(WECC_BOUNDS[1], WECC_BOUNDS[3])
    ax.set_aspect("auto")
    ax.set_axis_off()
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=OCEAN_COLOR)
    plt.close(fig)
    buf.seek(0)
    Image.open(buf).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(OUT_PATH)
    print(f"Done → {OUT_PATH}  ({len(networks)} networks)")


if __name__ == "__main__":
    main()
