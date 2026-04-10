"""
Shared utility for generating animated GIF icons from climakitae data.
"""

import io

import imageio.v3 as iio
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from dask.diagnostics import ProgressBar
from PIL import Image


def make_icon_gif(
    data,
    out_path,
    title,
    cmap="plasma",
    unit_label="",
    time_unit="h",
    vmin=None,
    vmax=None,
    kelvin_to_celsius=False,
    width=400,
    height=250,
    duration_ms=300,
    step=1,
):
    """
    Generate an animated GIF from an xarray Dataset or DataArray,
    styled with a black background and overlaid labels.

    Parameters
    ----------
    data : xr.Dataset or xr.DataArray
        Output from a climakitae .get() call.
    out_path : str
        Output file path for the GIF.
    title : str
        Label overlaid in the top-right corner. Use {timestamp} as a placeholder.
    cmap : str
        Matplotlib colormap name.
    unit_label : str
        Units shown in the bottom-right overlay.
    time_unit : str
        Numpy datetime unit for timestamp formatting ("h" for hourly, "D" for daily).
    vmin, vmax : float, optional
        Colorbar range. Defaults to data min/max.
    kelvin_to_celsius : bool
        If True and data looks like Kelvin (mean > 100), subtract 273.15.
    width, height : int
        Output GIF dimensions in pixels.
    duration_ms : int
        Duration of each frame in milliseconds.
    step : int
        Frame stride — e.g., step=3 uses every 3rd timestep.
    """
    if data is None:
        raise ValueError("Data is None — check your climakitae query parameters.")

    # Extract DataArray
    if hasattr(data, "data_vars"):
        var_name = list(data.data_vars)[0]
        da = data[var_name]
    else:
        da = data

    # Median across simulations for a representative single field
    if "sim" in da.dims:
        da = da.median(dim="sim")

    print("Loading data into memory …")
    with ProgressBar():
        da = da.compute()

    if kelvin_to_celsius and float(da.mean()) > 100:
        da = da - 273.15

    lon_name = "lon" if "lon" in da.coords else "longitude"
    lat_name = "lat" if "lat" in da.coords else "latitude"

    if vmin is None:
        vmin = float(da.min())
    if vmax is None:
        vmax = float(da.max())

    dpi = 200
    fig_w, fig_h = width / dpi, height / dpi

    frames = []
    time_dim = "time"
    n_times = da.sizes[time_dim]
    # For hourly data, skip the last frame (duplicate midnight); daily data uses all frames
    skip_last = time_unit == "h"
    n_frames = n_times - 1 if skip_last else n_times
    indices = range(0, n_frames, step)
    print(f"Generating {len(indices)} frames (step={step}) …")

    for i in indices:
        slice_da = da.isel({time_dim: i})
        timestamp = str(
            np.datetime_as_string(slice_da[time_dim].values, unit=time_unit)
        )

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        fig.set_facecolor("white")
        ax.set_facecolor("white")

        slice_da.plot.pcolormesh(
            ax=ax,
            x=lon_name,
            y=lat_name,
            vmin=vmin,
            vmax=vmax,
            cmap=cmap,
            add_colorbar=False,
        )

        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("")
        ax.xaxis.label.set_visible(False)
        ax.yaxis.label.set_visible(False)

        # Overlaid labels inside the plot
        ax.text(
            0.97,
            0.95,
            title.format(timestamp=timestamp),
            transform=ax.transAxes,
            fontsize=6,
            fontweight="bold",
            color="black",
            va="top",
            ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.5),
        )

        ax.tick_params(
            axis="both", direction="in", colors="black", labelsize=4, pad=-12
        )
        for spine in ax.spines.values():
            spine.set_visible(False)

        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0,
            facecolor="white",
        )
        plt.close(fig)
        buf.seek(0)
        img = Image.open(buf).convert("RGB").resize((width, height), Image.LANCZOS)
        frames.append(np.array(img))

        if len(frames) % 6 == 0 or len(frames) == len(indices):
            print(f"  frame {len(frames)}/{len(indices)}")

    print(f"Writing {out_path} …")
    iio.imwrite(out_path, frames, extension=".gif", duration=duration_ms, loop=0)
    print(f"Done → {out_path}  ({len(frames)} frames, {width}×{height} px)")
