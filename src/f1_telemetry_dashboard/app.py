from __future__ import annotations

import os
import datetime
import traceback

import fastf1
import pandas as pd
import plotly.graph_objects as go

from dash import Dash, Input, Output, State, dcc, html
import dash_bootstrap_components as dbc

from .config import TEAM_LOGO_MAP, load_settings
from .data import (
    get_available_events,
    get_driver_info,
    get_drivers_from_session,
    get_lap_telemetry,
    get_laps_for_driver,
    load_session_data,
)
from .report import build_report_docx_bytes, default_report_filename
from .utils import format_timedelta, image_to_base64, safe_int
from .viz import create_acceleration_map_base64, create_brake_throttle_plot, create_track_map_with_sectors


def create_app() -> Dash:
    settings = load_settings()

    # Enable cache
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(settings.cache_dir))

    # Optional mirror (keep user's env if set)
    os.environ.setdefault("FASTF1_API_MIRROR", os.environ.get("FASTF1_API_MIRROR", "livetiming-mirror.fastf1.dev"))

    current_year = datetime.datetime.now().year

    app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

    app.layout = dbc.Container(
        [
            dbc.Row([dbc.Col([html.H1("🏎️ F1 Телеметрия Дашборд", className="text-center my-4")])]),
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.H5("🔍 Параметры анализа", className="mb-3"),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    html.Label("Год"),
                                                                    dcc.Dropdown(
                                                                        id="year-dropdown",
                                                                        options=[
                                                                            {"label": y, "value": y}
                                                                            for y in range(2018, current_year + 1)
                                                                        ],
                                                                        value=current_year - 1,
                                                                        className="dropdown",
                                                                    ),
                                                                ],
                                                                width=2,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Label("Тип события"),
                                                                    dcc.Dropdown(
                                                                        id="event-type-dropdown",
                                                                        options=[
                                                                            {"label": "🏁 Гран-при", "value": "gp"},
                                                                            {"label": "🔧 Тесты", "value": "test"},
                                                                        ],
                                                                        value="gp",
                                                                        className="dropdown",
                                                                    ),
                                                                ],
                                                                width=2,
                                                            ),
                                                            dbc.Col(
                                                                [html.Label("Событие"), dcc.Dropdown(id="race-dropdown", className="dropdown")],
                                                                width=3,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Label("Сессия"),
                                                                    dcc.Dropdown(id="session-dropdown", className="dropdown"),
                                                                ],
                                                                width=2,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    html.Label("Гонщик"),
                                                                    dcc.Dropdown(id="driver-dropdown", className="dropdown"),
                                                                ],
                                                                width=2,
                                                            ),
                                                            dbc.Col(
                                                                [html.Label("Круг"), dcc.Dropdown(id="lap-dropdown", className="dropdown")],
                                                                width=1,
                                                            ),
                                                        ],
                                                        className="g-2 justify-content-between",
                                                    ),
                                                ]
                                            )
                                        ],
                                        className="card",
                                    )
                                ]
                            )
                        ]
                    )
                ],
                className="filters-container mb-4",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                id="driver-info",
                                style={"display": "flex", "alignItems": "center"},
                                children=[
                                    html.Img(
                                        id="driver-portrait",
                                        style={
                                            "height": "80px",
                                            "width": "80px",
                                            "borderRadius": "50%",
                                            "objectFit": "cover",
                                            "marginRight": "15px",
                                            "border": "2px solid #ddd",
                                        },
                                    ),
                                    html.Div([html.Div(id="driver-name", style={"fontSize": "20px", "fontWeight": "bold"})]),
                                ],
                            )
                        ],
                        width=6,
                    ),
                    dbc.Col(
                        [
                            html.Div(
                                id="team-info",
                                style={"display": "flex", "alignItems": "center", "justifyContent": "flex-end"},
                                children=[
                                    html.Div(
                                        [
                                            html.Div(
                                                id="team-name",
                                                style={
                                                    "fontSize": "18px",
                                                    "fontWeight": "600",
                                                    "marginRight": "15px",
                                                    "textAlign": "right",
                                                },
                                            )
                                        ]
                                    ),
                                    html.Img(id="team-logo", style={"height": "60px", "objectFit": "contain"}),
                                ],
                            )
                        ],
                        width=6,
                    ),
                ],
                className="mb-3",
            ),
            dbc.Row([dbc.Col([dbc.Card([dbc.CardBody([html.Div(id="stats-output")])], className="card mb-4")])]),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Button("📄 Скачать отчёт (DOCX)", id="export-report-btn", color="primary", className="w-100")
                        ],
                        width=3,
                    ),
                    dbc.Col(
                        [
                            html.Div(
                                "Отчёт включает: параметры, статистику круга, карту трассы, телеметрию и карту ускорений.",
                                className="text-muted",
                                style={"display": "flex", "alignItems": "center", "height": "100%"},
                            )
                        ],
                        width=9,
                    ),
                ],
                className="mb-4",
            ),
            dcc.Download(id="download-report"),
            dcc.Store(id="report-store"),
            dcc.Loading(
                id="loading-viz",
                type="circle",
                children=[
                    dbc.Row(
                        [
                            dbc.Col(
                                [dbc.Card([dbc.CardBody([dcc.Graph(id="track-map", style={"height": "500px"})])], className="card mb-4")],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.Img(
                                                        id="accel-map",
                                                        style={"width": "100%", "height": "500px", "objectFit": "contain"},
                                                    )
                                                ]
                                            )
                                        ],
                                        className="card mb-4",
                                    )
                                ],
                                width=6,
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [dbc.CardBody([dcc.Graph(id="brake-throttle-plot", style={"height": "500px"})])],
                                        className="card mb-4",
                                    )
                                ]
                            )
                        ]
                    ),
                ],
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Hr(),
                            html.P(
                                f"Данные FastF1 • Обновлено: {datetime.datetime.now().strftime('%d.%m.%Y')}",
                                className="text-center text-muted",
                            ),
                        ]
                    )
                ]
            ),
        ],
        fluid=True,
        style={"padding": "20px", "backgroundColor": "#f0f2f5"},
    )

    @app.callback(
        Output("race-dropdown", "options"),
        Output("race-dropdown", "value"),
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
    )
    def update_events(year, event_type):
        events = get_available_events(int(year), event_type)
        if events:
            return events, events[0]["value"]
        return [], None

    @app.callback(Output("session-dropdown", "options"), Output("session-dropdown", "value"), Input("event-type-dropdown", "value"))
    def update_sessions(event_type):
        if event_type == "test":
            return (
                [{"label": "Сессия 1", "value": "1"}, {"label": "Сессия 2", "value": "2"}, {"label": "Сессия 3", "value": "3"}],
                "1",
            )
        return (
            [
                {"label": "🏁 Гонка", "value": "R"},
                {"label": "⚡ Квалификация", "value": "Q"},
                {"label": "🔄 Практика 1", "value": "FP1"},
                {"label": "🔄 Практика 2", "value": "FP2"},
                {"label": "🔄 Практика 3", "value": "FP3"},
            ],
            "R",
        )

    @app.callback(
        Output("driver-dropdown", "options"),
        Output("driver-dropdown", "value"),
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("race-dropdown", "value"),
        Input("session-dropdown", "value"),
    )
    def update_drivers(year, event_type, race, session_id):
        if not all([year, race, session_id]):
            return [], None
        try:
            sess = load_session_data(int(year), str(race), str(session_id), event_type, load_full=False)
            drivers = get_drivers_from_session(sess)
            options = [{"label": d, "value": d} for d in drivers]
            value = drivers[0] if drivers else None
            return options, value
        except Exception as e:
            print(f"[ERROR] update_drivers: {e}")
            traceback.print_exc()
            return [], None

    @app.callback(
        Output("lap-dropdown", "options"),
        Output("lap-dropdown", "value"),
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("race-dropdown", "value"),
        Input("session-dropdown", "value"),
        Input("driver-dropdown", "value"),
    )
    def update_laps(year, event_type, race, session_id, driver_code):
        if not all([year, race, session_id, driver_code]):
            return [], None
        try:
            sess = load_session_data(int(year), str(race), str(session_id), event_type, load_full=False)
            laps_df = get_laps_for_driver(sess, str(driver_code))
            if laps_df.empty:
                return [], None
            laps = sorted(laps_df["LapNumber"].unique())
            safe_laps = [safe_int(lap) for lap in laps]
            options = [{"label": lap, "value": lap} for lap in safe_laps]
            value = safe_laps[0] if safe_laps else None
            return options, value
        except Exception as e:
            print(f"[ERROR] update_laps: {e}")
            traceback.print_exc()
            return [], None

    @app.callback(
        Output("stats-output", "children"),
        Output("track-map", "figure"),
        Output("brake-throttle-plot", "figure"),
        Output("accel-map", "src"),
        Output("driver-portrait", "src"),
        Output("driver-name", "children"),
        Output("team-logo", "src"),
        Output("team-name", "children"),
        Output("report-store", "data"),
        Input("year-dropdown", "value"),
        Input("event-type-dropdown", "value"),
        Input("race-dropdown", "value"),
        Input("session-dropdown", "value"),
        Input("driver-dropdown", "value"),
        Input("lap-dropdown", "value"),
    )
    def update_dashboard(year, event_type, race, session_id, driver_code, lap_num):
        if not all([year, race, session_id, driver_code, lap_num]):
            return "Выберите все параметры", go.Figure(), go.Figure(), "", None, "", None, "", {}

        try:
            sess = load_session_data(int(year), str(race), str(session_id), event_type, load_full=True)
            driver_info = get_driver_info(sess, str(driver_code))

            last_name = (driver_info.get("name") or str(driver_code)).split()[-1]
            portrait_path = settings.portrait_dir / (last_name[:3].lower() + ".jpg")
            portrait_src = image_to_base64(portrait_path)

            team_name = driver_info.get("team")
            team_key = TEAM_LOGO_MAP.get(team_name or "")
            logo_src = None
            if team_key:
                logo_src = image_to_base64(settings.team_logo_dir / f"{team_key}.png")

            laps_df = get_laps_for_driver(sess, str(driver_code))
            lap_data = laps_df[laps_df["LapNumber"] == lap_num] if not laps_df.empty else pd.DataFrame()
            if not lap_data.empty:
                lap_row = lap_data.iloc[0]
                lap_time = lap_row.get("LapTime", pd.NaT)
                compound = lap_row.get("Compound", "Unknown")
                tyre_life = lap_row.get("TyreLife", 0)
                s1 = lap_row.get("Sector1Time", pd.NaT)
                s2 = lap_row.get("Sector2Time", pd.NaT)
                s3 = lap_row.get("Sector3Time", pd.NaT)  # keep as-is
                pit_stops = len(laps_df[laps_df["PitInTime"].notna() & (laps_df["LapNumber"] < lap_num)])
            else:
                lap_time = pd.NaT
                compound = "N/A"
                tyre_life = 0
                s1 = s2 = s3 = pd.NaT
                pit_stops = 0

            stats = dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H6("🏁 Круг", className="text-muted"),
                                        html.H3(f"{safe_int(lap_num)}", className="fw-bold"),
                                    ],
                                    style={
                                        "minHeight": "120px",
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "justifyContent": "center",
                                    },
                                )
                            ],
                            className="text-center",
                        ),
                        width=2,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H6("⏱️ Время круга", className="text-muted"),
                                        html.H3(
                                            f"{format_timedelta(lap_time)}",
                                            className="fw-bold",
                                            style={"color": "#1E88E5"},
                                        ),
                                    ],
                                    style={
                                        "minHeight": "120px",
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "justifyContent": "center",
                                    },
                                )
                            ],
                            className="text-center",
                        ),
                        width=2,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H6("🔘 Шины", className="text-muted"),
                                        html.H3(compound, className="fw-bold"),
                                        html.Small(f"износ: {tyre_life} кр."),
                                    ],
                                    style={
                                        "minHeight": "120px",
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "justifyContent": "center",
                                    },
                                )
                            ],
                            className="text-center",
                        ),
                        width=2,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [html.H6("⛽ Пит-стопы", className="text-muted"), html.H3(pit_stops, className="fw-bold")],
                                    style={
                                        "minHeight": "120px",
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "justifyContent": "center",
                                    },
                                )
                            ],
                            className="text-center",
                        ),
                        width=2,
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H6("📊 Сектора", className="text-muted"),
                                        html.Div(
                                            [
                                                html.Span("S1: ", style={"color": "#FF4C4C"}),
                                                html.Span(f"{format_timedelta(s1)} "),
                                                html.Span("S2: ", style={"color": "#4C7BFF"}),
                                                html.Span(f"{format_timedelta(s2)} "),
                                                html.Span("S3: ", style={"color": "#4CAF50"}),
                                                html.Span(f"{format_timedelta(s3)}"),
                                            ]
                                        ),
                                    ],
                                    style={
                                        "minHeight": "120px",
                                        "display": "flex",
                                        "flexDirection": "column",
                                        "justifyContent": "center",
                                    },
                                )
                            ]
                        ),
                        width=4,
                    ),
                ]
            )

            telemetry = pd.DataFrame()
            s1_time = None
            s2_time = None
            circuit_info = None
            try:
                telemetry, lap_obj, circuit_info = get_lap_telemetry(sess, str(driver_code), safe_int(lap_num))
                s1_time = getattr(lap_obj, "Sector1Time", None)
                s2_time = getattr(lap_obj, "Sector2Time", None)
            except Exception as e:
                print(f"[WARN] telemetry error: {e}")

            track_fig = create_track_map_with_sectors(telemetry, circuit_info, s1_time=s1_time, s2_time=s2_time)
            brake_fig = create_brake_throttle_plot(telemetry)
            accel_b64 = create_acceleration_map_base64(telemetry)
            accel_src = f"data:image/png;base64,{accel_b64}" if accel_b64 else ""

            report_data = {
                "year": int(year),
                "event_type": event_type,
                "event": str(race),
                "session": str(session_id),
                "driver_code": str(driver_code),
                "driver_name": driver_info.get("name"),
                "team": driver_info.get("team"),
                "lap_num": safe_int(lap_num),
                "lap_time": format_timedelta(lap_time),
                "sector1": format_timedelta(s1),
                "sector2": format_timedelta(s2),
                "sector3": format_timedelta(s3),
                "compound": compound,
                "tyre_life": tyre_life,
                "pit_stops_before": pit_stops,
                "portrait_src": portrait_src,
                "team_logo_src": logo_src,
            }

            return stats, track_fig, brake_fig, accel_src, portrait_src, driver_info["name"], logo_src, driver_info["team"], report_data
        except Exception as e:
            print(f"[DASHBOARD ERROR] {e}")
            traceback.print_exc()
            return dbc.Alert(f"Ошибка: {e}", color="danger"), go.Figure(), go.Figure(), "", None, "", None, "", {}

    @app.callback(
        Output("download-report", "data"),
        Input("export-report-btn", "n_clicks"),
        State("report-store", "data"),
        State("track-map", "figure"),
        State("brake-throttle-plot", "figure"),
        State("accel-map", "src"),
        prevent_initial_call=True,
    )
    def export_report(_n, report_data, track_fig_dict, brake_fig_dict, accel_src):
        if not report_data:
            return None
        try:
            docx_bytes = build_report_docx_bytes(report_data, track_fig_dict, brake_fig_dict, accel_src)
            filename = default_report_filename(report_data)
            return dcc.send_bytes(
                docx_bytes,
                filename,
                type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            print(f"[REPORT] Failed to build docx: {e}")
            traceback.print_exc()
            return None

    return app

