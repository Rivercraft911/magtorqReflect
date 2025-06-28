#!/usr/bin/env python3
"""
This script allows you to interactively test the power consumption of the MTQ‑800
by setting various dipole moments and measuring the power consumption at each level.
"""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import csv
import logging
import time
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import serial

from magtorquer.mtq_driver import MTQDriver, MTQCommunicationError
from magtorquer.config_mtq import (
    SERIAL_PORT, BAUD_RATE, SERIAL_TIMEOUT, HOST_ADDRESS, MTQ_ADDRESS,
    TEST_LEVELS_MAM2, STABILIZATION_DELAY_S, RECOMMENDED_MAX_MAM2,
)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)-8s - %(message)s")
logger = logging.getLogger("power_test")

# Background watchdog‑ping thread
class WatchdogPatter(threading.Thread):
    """Keeps the watchdog alive with periodic PINGs."""

    def __init__(self, driver: MTQDriver, stop_event: threading.Event, interval_s: float = 4.0):
        super().__init__(daemon=True)
        self.driver, self.stop_event, self.interval = driver, stop_event, interval_s
        self.name = "WatchdogPatter"

    def run(self) -> None:  # noqa: D401  (imperative style)
        logger.debug("Watchdog thread started.")
        while not self.stop_event.wait(self.interval):
            try:
                self.driver.ping()
            except MTQCommunicationError as exc:  # pragma: no cover  (debug aid)
                logger.warning("Background ping failed: %s", exc)
        logger.debug("Watchdog thread stopped.")

# Data container
@dataclass(slots=True)
class TestResult:
    setpoint_mAm2: float
    measured_moment_mAm2: float
    measured_watts: float

    @property
    def measured_moment_Am2(self) -> float:  # helper for plot conversion
        return self.measured_moment_mAm2 / 1_000.0

# Helper I/O

def prompt_power_reading(setpoint: int) -> float:
    """Ask user to type the power (W). Keeps asking until float parses."""
    while True:
        try:
            return float(input(f" >> Power at {setpoint:5d} mAm² (W): "))
        except ValueError:
            logger.warning("Please enter a numeric value, e.g. 3.85")

# Plotting

def plot_results(results: list[TestResult]) -> None:
    """Plot and save the power curve, showing wattage labels at each point."""
    # Sort results so the line is monotonic left→right
    results = sorted(results, key=lambda r: r.measured_moment_Am2)

    x = [r.measured_moment_Am2 for r in results]
    y = [r.measured_watts       for r in results]
    labels = [f"{w:.2f} W"      for w in y]   # ← new

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x,
        y=y,
        mode="lines+markers+text",           # ← include “text”
        line=dict(width=3),
        marker=dict(size=9),
        text=labels,                         # ← new
        textposition="top center",           # ← change to taste
        textfont=dict(size=14),
        name="Measured",
        hovertemplate="<b>Moment</b>: %{x:.2f} Am²<br><b>Power</b>: %{y:.3f} W<extra></extra>",
    ))

    # Nominal‑max vertical line (converted to Am²)
    v_nom = RECOMMENDED_MAX_MAM2 / 1_000.0
    fig.add_vline(x=v_nom, line_width=2, line_dash="dash", line_color="green")
    fig.add_annotation(x=v_nom, y=max(y)*0.5, text="Nominal&nbsp;Max", showarrow=True,
                      arrowhead=1, ax=-60, ay=-40, font=dict(color="green"))

    # Saturation detection: if last three points within ±2 %, draw a horizontal line.
    if len(x) >= 4 and max(x[-3:]) - min(x[-3:]) < 0.02 * x[-1]:
        sat_y = sum(y[-3:]) / 3
        fig.add_hline(y=sat_y, line_dash="dot", line_color="red",
                      annotation_text="Dipole saturation", annotation_position="top left")

    fig.update_layout(
        title="MTQ800.15 – Power vs Dipole Moment",
        xaxis_title="Measured Dipole Moment (Am²)",
        yaxis_title="Power Consumption (W)",
        template="plotly_white",
        font=dict(size=16, family="Arial"),
        margin=dict(l=80, r=40, t=80, b=60),
    )

    out_png = Path("mtq_power_profile.png")
    try:
        fig.write_image(out_png, width=1000, height=600, scale=2)
        logger.info("Saved curve → %s", out_png)
    except Exception as exc:  # pragma: no cover  (env‑specific)
        logger.warning("Could not write PNG (need 'kaleido' ororca). Error: %s", exc)
    fig.show()

# CSV archiving

def save_csv(results: list[TestResult]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(f"power_profile_{ts}.csv")
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["setpoint_mAm2", "measured_moment_mAm2", "measured_watts"])
        for r in results:
            writer.writerow([r.setpoint_mAm2, r.measured_moment_mAm2, r.measured_watts])
    logger.info("Logged raw measurements → %s", path)
    return path

# Main interactive routine

def run_test() -> None:
    print("\n" + "="*78)
    print("MTQ800.15 Interactive Power Profile Test")
    print("(Watchdog is pinged in background – you can take your time.)")
    print("="*78 + "\n")

    results: list[TestResult] = []
    try:
        with MTQDriver(SERIAL_PORT, BAUD_RATE, HOST_ADDRESS, MTQ_ADDRESS, SERIAL_TIMEOUT) as drv:
            drv.stop(); drv.set_dipole_moment(0.0)
            if not drv.who_am_i():
                logger.error("MTQ did not respond to WHO_AM_I – aborting.")
                return

            for idx, sp in enumerate(TEST_LEVELS_MAM2, start=1):
                print(f"\n--- Level {idx}/{len(TEST_LEVELS_MAM2)} – Set {sp} mAm² "
                      + "-"*(60 - len(str(sp))))
                drv.set_dipole_moment(float(sp))
                if idx == 2: drv.start()
                time.sleep(STABILIZATION_DELAY_S)
                meas = drv.get_dipole_moment() or 0
                logger.info("Device reports %.0f mAm²", meas)

                stop_evt = threading.Event(); patter = WatchdogPatter(drv, stop_evt)
                patter.start()
                pwr = prompt_power_reading(sp)
                stop_evt.set(); patter.join()

                results.append(TestResult(sp, meas, pwr))

            drv.set_dipole_moment(0.0); drv.stop()

    except (MTQCommunicationError, serial.SerialException) as exc:
        logger.error("Communication error: %s", exc)
    except Exception:  # noqa: BLE001  (log unexpected)
        logger.exception("Unexpected error:")
    finally:
        if results:
            save_csv(results)
            plot_results(results)
        else:
            logger.warning("No data collected – nothing to plot.")

if __name__ == "__main__":
    run_test()
