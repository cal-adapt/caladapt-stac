"""
Generate a static PNG icon showing sea level rise (wl_slr) at San Francisco
across three SSP emission scenarios (ssp245, ssp370, ssp585), annual means
averaged over all ensemble members.
"""

import io
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import s3fs
import xarray as xr
from PIL import Image

from icon_constants import WIDTH, HEIGHT, DPI, title_kwargs

SCALE = 3
OUT_PATH = "sea_level_icon.png"

SLR_SCENARIOS = ["low", "int", "hig"]
COLORS = {"low": "#4e9ec2", "int": "#f4a43a", "hig": "#d64545"}
LABELS = {"low": "Low", "int": "Intermediate", "hig": "High"}


def load_annual_slr(fs, station, slr_scenario, ssp):
    key = f"cadcat/hmet/watlev.{station}.{slr_scenario}.50pctile.{ssp}.wv2.nc"
    print(f"  Loading {key} ...")
    with fs.open(key) as f:
        ds = xr.open_dataset(f)
        time_vals = ds["time"].values
        wl_slr = ds["wl_slr"].values  # (ensemble, nt)

    da = xr.DataArray(
        wl_slr,
        dims=["ensemble", "time"],
        coords={"time": time_vals},
    )
    annual = da.resample(time="YE").mean()
    return annual.mean(dim="ensemble")  # (years,)


def main():
    fs = s3fs.S3FileSystem(anon=True)

    # Render at 3x resolution then downscale for crispness
    scale = SCALE
    dpi = DPI
    fig, ax = plt.subplots(figsize=(WIDTH * scale / dpi, HEIGHT * scale / dpi), dpi=dpi)
    fig.set_facecolor("white")
    ax.set_facecolor("white")

    for slr in SLR_SCENARIOS:
        da = load_annual_slr(fs, station="sf", slr_scenario=slr, ssp="ssp370")
        ax.plot(
            da.time.values,
            da.values,
            color=COLORS[slr],
            linewidth=4,
            label=LABELS[slr],
        )

    fs = title_kwargs(SCALE)["fontsize"]  # base fontsize for this scale
    ax.set_xlabel("")
    ax.set_ylabel("Sea level rise (m)", fontsize=fs, color="#333333")
    ax.set_title("Sea level rise — San Francisco", fontsize=fs, color="#333333", pad=10)
    ax.tick_params(axis="both", labelsize=fs * 0.85, colors="#555555")
    ax.legend(
        fontsize=fs * 0.85,
        loc="upper left",
        framealpha=0.7,
        title="SLR scenario",
        title_fontsize=fs * 0.85,
        edgecolor="#cccccc",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.yaxis.grid(True, color="#eeeeee", linewidth=1.5, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    Image.open(buf).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS).save(OUT_PATH)
    print(f"Done → {OUT_PATH}")


if __name__ == "__main__":
    main()
