from __future__ import annotations

import base64
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .utils import is_valid_td


def _get_theme_colors(theme: str | None) -> dict[str, str]:
    theme = (theme or "light").lower()
    if theme == "dark":
        return {
            "plot_bg": "#111111",
            "paper_bg": "#111111",
            "font": "#FFFFFF",
            "grid": "#333333",
            "legend_bg": "rgba(17,17,17,0.9)",
        }
    return {
        "plot_bg": "#f8f9fa",
        "paper_bg": "#FFFFFF",
        "font": "#000000",
        "grid": "#e0e0e0",
        "legend_bg": "rgba(255,255,255,0.9)",
    }


def create_track_map_with_sectors(
    telemetry: pd.DataFrame,
    circuit_info=None,
    s1_time=None,
    s2_time=None,
    theme: str = "light",
) -> go.Figure:
    fig = go.Figure()
    colors = _get_theme_colors(theme)

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
                    textfont=dict(size=10, color=colors["font"]),
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
        title=dict(text="Карта трассы", font=dict(size=18, family="Inter", color=colors["font"]), x=0.5),
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=70),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            bgcolor=colors["legend_bg"],
            bordercolor="black",
            borderwidth=1,
        ),
        plot_bgcolor=colors["plot_bg"],
        paper_bgcolor=colors["paper_bg"],
        font=dict(color=colors["font"]),
    )
    return fig


def create_brake_throttle_plot(telemetry: pd.DataFrame, theme: str = "light") -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = _get_theme_colors(theme)
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
        title=dict(text="Телеметрия круга", font=dict(size=18, family="Inter", color=colors["font"]), x=0.5),
        hovermode="x unified",
        plot_bgcolor=colors["plot_bg"],
        paper_bgcolor=colors["paper_bg"],
        font=dict(color=colors["font"]),
    )
    fig.update_xaxes(title_text="Дистанция (м)", gridcolor=colors["grid"])
    fig.update_yaxes(title_text="Газ (%)", secondary_y=False, range=[0, 110], gridcolor=colors["grid"])
    fig.update_yaxes(title_text="Скорость (км/ч)", secondary_y=True, gridcolor=colors["grid"])
    return fig


def create_acceleration_map_figure(telemetry: pd.DataFrame, theme: str = "light") -> go.Figure:
    colors = _get_theme_colors(theme)

    fig = go.Figure()

    def _apply_common_layout(target_fig: go.Figure, message: str | None = None) -> None:
        if message:
            target_fig.add_annotation(
                text=message,
                showarrow=False,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                font=dict(size=16, family="Inter", color=colors["font"]),
            )
        target_fig.update_xaxes(visible=False)
        target_fig.update_yaxes(visible=False)
        target_fig.update_layout(
            title=dict(
                text="Торможения (зелёный) / Ускорения (красный)",
                font=dict(size=18, family="Inter", color=colors["font"]),
                x=0.5,
            ),
            margin=dict(l=0, r=0, t=50, b=20),
            plot_bgcolor=colors["plot_bg"],
            paper_bgcolor=colors["paper_bg"],
            font=dict(color=colors["font"]),
        )

    if (
        telemetry is None
        or telemetry.empty
        or "Speed" not in telemetry.columns
        or "Time" not in telemetry.columns
    ):
        _apply_common_layout(fig, "Нет данных телеметрии")
        return fig

    if not all(col in telemetry.columns for col in ["X", "Y"]):
        _apply_common_layout(fig, "Нет координат трассы")
        return fig

    dt = telemetry["Time"].diff().dt.total_seconds()
    dv = telemetry["Speed"].diff()
    acc = dv / dt

    df = telemetry.copy()
    df["acc"] = acc
    df = df.dropna(subset=["X", "Y", "acc"]).sort_values("Time")

    if len(df) < 2:
        _apply_common_layout(fig, "Недостаточно точек")
        return fig

    # Clamp accelerations for a stable color scale
    acc_vals = df["acc"].to_numpy()
    acc_min, acc_max = -20, 20
    acc_clamped = np.clip(acc_vals, acc_min, acc_max)

    fig.add_trace(
        go.Scatter(
            x=df["X"],
            y=df["Y"],
            mode="markers",
            marker=dict(
                size=6,
                color=acc_clamped,
                colorscale="RdYlGn_r",
                cmin=acc_min,
                cmax=acc_max,
                colorbar=dict(
                    title=dict(text="Ускорение (км/ч/с)", side="right"),
                ),
            ),
            hovertemplate=(
                "X: %{x:.1f}<br>"
                "Y: %{y:.1f}<br>"
                "Ускорение: %{marker.color:.2f} км/ч/с"
                "<extra></extra>"
            ),
            name="Ускорение",
        )
    )

    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False)
    _apply_common_layout(fig)
    return fig


def create_acceleration_map_base64(telemetry: pd.DataFrame, theme: str = "light") -> str:
    """
    Сохранён для обратной совместимости: строит ту же фигуру, но
    возвращает PNG в base64 (например, для отчётов).
    """
    fig = create_acceleration_map_figure(telemetry, theme=theme)
    try:
        img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
    except Exception as e:  # pragma: no cover - safety net вокруг kaleido
        print(f"[VIZ] Failed to render acceleration map via plotly: {e}")
        return ""

    return base64.b64encode(img_bytes).decode("utf-8")

