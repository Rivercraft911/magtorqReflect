#!/usr/bin/env python3
"""
Plot MTQ‑800.15 power‑profile data with Plotly.

Usage
-----
python plot_power_profile.py path/to/results.csv
    – CSV must contain 'moment_mAm2,power_W' header.

python plot_power_profile.py               # uses DATA list below
"""

from __future__ import annotations
import csv, sys, pathlib, datetime, textwrap
import plotly.graph_objects as go

# ----------------------------------------------------------------------
# 1)  If a CSV path is given on the command‑line, load it:
DATA: list[tuple[int, float]] = []
if len(sys.argv) >= 2:
    csv_path = pathlib.Path(sys.argv[1]).expanduser()
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            DATA.append((int(row["moment_mAm2"]), float(row["power_W"])))

# 2)  Otherwise fall back to an inline list:
if not DATA:
    DATA = [
        (0,     0.12),  (1964,   0.48),  (3632,  0.72),
        (4977,  0.96),  (7380,   1.44),  (8914,  1.68),
        (11172, 2.16),  (14997,  3.12),  (19948, 4.68),
        (24935, 6.84),  (29986,  9.48),
    ]

# ----------------------------------------------------------------------
#  Convert & sort
DATA.sort(key=lambda t: t[0])
moment_Am2 = [m / 1000 for m, _ in DATA]    # mAm² → A·m²
power_W    = [w           for _, w in DATA]

# ----------------------------------------------------------------------
#  Plotly figure
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=moment_Am2,
        y=power_W,
        mode="lines+markers",
        line=dict(width=2),
        marker=dict(size=8),
        name="Measured Power",
        hovertemplate="<b>Moment</b>: %{x:.2f} A·m²<br><b>Power</b>: %{y:.2f} W<extra></extra>",
    )
)

# Nominal–boost boundary @ 20 k mAm² = 20 A·m²
BOOST_BOUND = 20_000           # mAm²
boost_A = BOOST_BOUND / 1000   # A·m²

fig.add_vline(x=boost_A,
              line_width=2, line_dash="dash", line_color="green",
              annotation_text="Nominal / Boost", annotation_position="top left")

# Shade boost region (x > 20 A·m²)
max_x = max(moment_Am2)
fig.add_vrect(x0=boost_A, x1=max_x,
              fillcolor="red", opacity=0.12, line_width=0,
              annotation_text="Boost Region", annotation_position="top left")

# Layout tweaks
fig.update_layout(
    title="MTQ‑800.15 Power vs. Dipole Moment",
    xaxis_title="Measured Dipole Moment (A·m²)",
    yaxis_title="Power Consumption (W)",
    template="plotly_white",
    font=dict(family="Arial", size=14),
    margin=dict(l=60, r=50, t=60, b=60),
)

# ----------------------------------------------------------------------
#  Save outputs
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
fname_base = f"mtq_power_profile_{ts}"
fig.write_html(fname_base + ".html")
fig.write_image(fname_base + ".png", width=1000, height=600, scale=2)

print(textwrap.dedent(f"""
    Saved:
      • {fname_base}.html  (interactive)
      • {fname_base}.png   (hi‑res static)

    Open the HTML in a browser for hover‑tool‑tips and zoom.
"""))
