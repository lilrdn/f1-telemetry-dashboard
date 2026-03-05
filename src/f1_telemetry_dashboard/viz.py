from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from .utils import is_valid_td


def create_track_map_with_sectors(telemetry: pd.DataFrame, circuit_info=None, s1_time=None, s2_time=None) -> go.Figure:
    fig = go.Figure()

    if telemetry is None or telemetry.empty:
        return fig
    required = {"Time", "Distance", "X", "Y"}
    if not required.issubset(set(telemetry.columns)):
        return fig

    valid = telemetry.dropna(subset=["X", "Y"]).copy()
    if valid.empty:
        return fig

    valid = valid.sort_values("Time").reset_index(drop=True)

    t0 = valid["Time"].iloc[0]
    rel_t = (valid["Time"] - t0).dt.total_seconds()

    s1_idx = None
    s2_idx = None

    if is_valid_td(s1_time):
        try:
            s1_val = s1_time.iloc[0] if isinstance(s1_time, (pd.Series, pd.Index, np.ndarray)) else s1_time
            s1_seconds = s1_val.total_seconds()
            s1_idx = int((rel_t - s1_seconds).abs().idxmin())
        except Exception as e:
            print(f"[SECTORS] cannot compute S1 index: {e}")
            s1_idx = None

    if is_valid_td(s1_time) and is_valid_td(s2_time):
        try:
            s1_val = s1_time.iloc[0] if isinstance(s1_time, (pd.Series, pd.Index, np.ndarray)) else s1_time
            s2_val = s2_time.iloc[0] if isinstance(s2_time, (pd.Series, pd.Index, np.ndarray)) else s2_time
            s2_seconds = s1_val.total_seconds() + s2_val.total_seconds()
            s2_idx = int((rel_t - s2_seconds).abs().idxmin())
        except Exception as e:
            print(f"[SECTORS] cannot compute S2 index: {e}")
            s2_idx = None

    if (s1_idx is None) or (s2_idx is None) or (s1_idx >= s2_idx):
        total_dist = valid["Distance"].max()
        if not np.isfinite(total_dist) or total_dist <= 0:
            return fig

        s1_end = total_dist / 3
        s2_end = 2 * total_dist / 3

        mask_s1 = valid["Distance"] <= s1_end
        idx_s1_last = valid[mask_s1].index[-1]
        mask_s2 = (valid.index >= idx_s1_last) & (valid["Distance"] <= s2_end)
        idx_s2_last = valid[valid["Distance"] <= s2_end].index[-1]
        mask_s3 = valid.index >= idx_s2_last
    else:
        mask_s1 = valid.index <= s1_idx
        mask_s2 = (valid.index > s1_idx) & (valid.index <= s2_idx)
        mask_s3 = valid.index > s2_idx

    if mask_s1.any():
        fig.add_trace(
            go.Scatter(
                x=valid.loc[mask_s1, "X"],
                y=valid.loc[mask_s1, "Y"],
                mode="lines",
                line=dict(color="#FF4C4C", width=3),
                name="Сектор 1",
            )
        )
    if mask_s2.any():
        fig.add_trace(
            go.Scatter(
                x=valid.loc[mask_s2, "X"],
                y=valid.loc[mask_s2, "Y"],
                mode="lines",
                line=dict(color="#4C7BFF", width=3),
                name="Сектор 2",
            )
        )
    if mask_s3.any():
        fig.add_trace(
            go.Scatter(
                x=valid.loc[mask_s3, "X"],
                y=valid.loc[mask_s3, "Y"],
                mode="lines",
                line=dict(color="#4CAF50", width=3),
                name="Сектор 3",
            )
        )

    if circuit_info is not None and hasattr(circuit_info, "corners"):
        for _, corner in circuit_info.corners.iterrows():
            fig.add_trace(
                go.Scatter(
                    x=[corner["X"]],
                    y=[corner["Y"]],
                    mode="markers+text",
                    marker=dict(size=8, color="white", line=dict(color="black", width=1)),
                    text=corner["Number"],
                    textfont=dict(size=10, color="black"),
                    textposition="top center",
                    showlegend=False,
                )
            )

    try:
        start_idx = valid["Distance"].idxmin()
        fig.add_trace(
            go.Scatter(
                x=[valid.loc[start_idx, "X"]],
                y=[valid.loc[start_idx, "Y"]],
                mode="markers",
                marker=dict(size=15, color="#FFD700", symbol="star", line=dict(color="black", width=1)),
                name="Старт/финиш",
            )
        )
    except Exception:
        pass

    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        title=dict(text="🏁 Карта трассы", font=dict(size=18, family="Inter"), x=0.5),
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=70),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="black",
            borderwidth=1,
        ),
        plot_bgcolor="#f8f9fa",
        paper_bgcolor="white",
    )
    return fig


def create_brake_throttle_plot(telemetry: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if telemetry is None or telemetry.empty:
        return fig
    if "Distance" not in telemetry.columns:
        return fig

    fig.add_trace(
        go.Scatter(
            x=telemetry["Distance"],
            y=telemetry.get("Throttle", 0),
            mode="lines",
            name="Газ",
            line=dict(color="#4CAF50", width=2),
        ),
        secondary_y=False,
    )

    if "Brake" in telemetry.columns:
        brake_on = telemetry[telemetry["Brake"] == True]
        if not brake_on.empty:
            fig.add_trace(
                go.Scatter(
                    x=brake_on["Distance"],
                    y=[100] * len(brake_on),
                    mode="markers",
                    name="Тормоз",
                    marker=dict(color="#FF4C4C", size=4, symbol="circle"),
                ),
                secondary_y=False,
            )

    if "Speed" in telemetry.columns:
        fig.add_trace(
            go.Scatter(
                x=telemetry["Distance"],
                y=telemetry["Speed"],
                mode="lines",
                name="Скорость",
                line=dict(color="#1E88E5", width=2),
            ),
            secondary_y=True,
        )

    fig.update_layout(
        title=dict(text="📊 Телеметрия круга", font=dict(size=18, family="Inter"), x=0.5),
        hovermode="x unified",
        plot_bgcolor="#f8f9fa",
        paper_bgcolor="white",
    )
    fig.update_xaxes(title_text="Дистанция (м)", gridcolor="#e0e0e0")
    fig.update_yaxes(title_text="Газ (%)", secondary_y=False, range=[0, 110], gridcolor="#e0e0e0")
    fig.update_yaxes(title_text="Скорость (км/ч)", secondary_y=True, gridcolor="#e0e0e0")
    return fig


def create_acceleration_map_base64(telemetry: pd.DataFrame) -> str:
    if telemetry is None or telemetry.empty or "Speed" not in telemetry.columns or "Time" not in telemetry.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "Нет данных телеметрии", ha="center", va="center")
        ax.axis("off")
    else:
        dt = telemetry["Time"].diff().dt.total_seconds()
        dv = telemetry["Speed"].diff()
        acc = dv / dt

        if not all(col in telemetry.columns for col in ["X", "Y"]):
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "Нет координат трассы", ha="center", va="center")
            ax.axis("off")
        else:
            x = telemetry["X"].values
            y = telemetry["Y"].values
            acc = acc.values
            mask = ~np.isnan(acc)
            x = x[mask]
            y = y[mask]
            acc = acc[mask]
            if len(x) < 2:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.text(0.5, 0.5, "Недостаточно точек", ha="center", va="center")
                ax.axis("off")
            else:
                points = np.array([x, y]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                fig, ax = plt.subplots(figsize=(8, 6), facecolor="white")
                norm = plt.Normalize(-20, 20)
                lc = LineCollection(segments, cmap="RdYlGn_r", norm=norm, linewidth=3)
                lc.set_array(acc[:-1])
                ax.add_collection(lc)
                ax.set_xlim(x.min(), x.max())
                ax.set_ylim(y.min(), y.max())
                ax.set_title("Торможения (зеленый) / Ускорения (красный)", fontsize=14, fontweight="bold")
                ax.axis("equal")
                ax.axis("off")
                ax.set_facecolor("#f8f9fa")
                plt.colorbar(lc, ax=ax, label="Ускорение (км/ч/с)", shrink=0.8, pad=0.05)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    return base64.b64encode(buf.read()).decode("utf-8")

