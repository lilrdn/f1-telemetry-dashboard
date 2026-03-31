from __future__ import annotations

import time
import traceback
from typing import Any

import fastf1
import pandas as pd

from .config import DRIVER_DB


def get_available_events(year: int, event_type: str = "gp") -> list[dict[str, str]]:
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=(event_type == "test"))
        if event_type == "test":
            testing = schedule[schedule["RoundNumber"] == 0]
            events: list[dict[str, str]] = []
            for _, row in testing.iterrows():
                test_num = len(events) + 1
                events.append({"label": f"Тест {test_num}: {row['EventName']}", "value": str(test_num)})
            return events

        races = schedule[schedule["RoundNumber"] > 0]
        return [{"label": row["EventName"], "value": row["EventName"]} for _, row in races.iterrows()]
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки событий: {e}")
        return []


def load_session_data(
    year: int,
    event_id: str,
    session_id: str,
    event_type: str = "gp",
    load_full: bool = False,
):
    print(f"\n[LOAD] {year}, {event_type}, {event_id}, {session_id}, full={load_full}")
    start = time.time()
    try:
        if event_type == "test":
            test_num = int(event_id)
            session_num = int(session_id)
            session = fastf1.get_testing_session(year, test_num, session_num)
            session.load(laps=True, telemetry=load_full, weather=load_full)
        else:
            schedule = fastf1.get_event_schedule(year)
            event_row = schedule[schedule["EventName"].str.contains(event_id, case=False, na=False)]
            if event_row.empty:
                event_row = schedule[schedule["Country"].str.contains(event_id, case=False, na=False)]
            round_num = int(event_row.iloc[0]["RoundNumber"]) if not event_row.empty else event_id
            session = fastf1.get_session(year, round_num, session_id)
            session.load(laps=True, telemetry=load_full, weather=load_full)
        laps_count = len(session.laps) if session.laps is not None else 0
        print(f"[LOAD] Готово за {time.time()-start:.1f} сек, кругов: {laps_count}")
        return session
    except Exception as e:
        print(f"[LOAD] Ошибка: {e}")
        traceback.print_exc()
        raise


def get_drivers_from_session(session) -> list[str]:
    try:
        driver_numbers = getattr(session, "drivers", [])
        if not driver_numbers:
            print("[WARN] session.drivers is empty")
            return []
        drivers: list[str] = []
        for num in driver_numbers:
            try:
                info = session.get_driver(num)
                abb = info.get("Abbreviation")
                if abb:
                    drivers.append(abb)
            except Exception as e:
                print(f"[WARN] Could not get driver info for {num}: {e}")
        return sorted(set(drivers))
    except Exception as e:
        print(f"[ERROR] get_drivers_from_session: {e}")
        return []


def get_laps_for_driver(session, driver_code: str) -> pd.DataFrame:
    try:
        if session.laps is None:
            return pd.DataFrame()
        laps_df = pd.DataFrame(session.laps)
        if laps_df.empty:
            return pd.DataFrame()
        return laps_df[laps_df["Driver"] == driver_code]
    except Exception as e:
        print(f"[ERROR] get_laps_for_driver: {e}")
        return pd.DataFrame()


def get_driver_info(session, driver_code: str) -> dict[str, Any]:
    try:
        driver_numbers = getattr(session, "drivers", [])
        driver_info: dict[str, Any] | None = None

        for num in driver_numbers:
            try:
                info = session.get_driver(num)
                if info.get("Abbreviation") == driver_code:
                    driver_info = info
                    break
            except Exception:
                continue

        if driver_info is None:
            try:
                driver_info = session.get_driver(driver_code)
            except Exception:
                driver_info = {}

        first = driver_info.get("FirstName", "")
        last = driver_info.get("LastName", "")
        full_name = f"{first} {last}".strip() or driver_code

        team = "Unknown"
        try:
            if session.laps is not None:
                laps_df = pd.DataFrame(session.laps)
                if not laps_df.empty:
                    laps_driver = laps_df[laps_df["Driver"] == driver_code]
                    if not laps_driver.empty:
                        team = laps_driver.iloc[0].get("Team", "Unknown")
        except Exception:
            pass

        try:
            color = fastf1.plotting.get_driver_color(driver_code, session)
        except Exception:
            color = "#808080"

        return {
            "name": full_name,
            "number": driver_info.get("DriverNumber", "N/A"),
            "team": team,
            "color": color,
        }
    except Exception as e:
        print(f"[ERROR] get_driver_info: {e}")
        return DRIVER_DB.get(driver_code, {"name": driver_code, "team": "Unknown", "color": "#808080"})


def get_lap_telemetry(session, driver_code: str, lap_num: int) -> tuple[pd.DataFrame, Any, Any]:
    """
    Returns (telemetry_df, lap_obj, circuit_info)
    telemetry_df columns: Time, Distance, Speed, Throttle, Brake, X, Y (if available)
    """
    # FastF1 deprecations: pick_driver/pick_lap -> pick_drivers/pick_laps
    lap_obj = session.laps.pick_drivers([driver_code]).pick_laps([lap_num])
    if hasattr(lap_obj, "iloc"):
        lap_obj = lap_obj.iloc[0]
    car_data = lap_obj.get_car_data().add_distance()
    pos_data = lap_obj.get_pos_data()

    telemetry = car_data[["Time", "Distance", "Speed", "Throttle", "Brake"]].copy()
    if pos_data is not None and not pos_data.empty:
        pos = pos_data[["Time", "X", "Y"]].copy()
        telemetry = pd.merge_asof(
            telemetry.sort_values("Time"),
            pos.sort_values("Time"),
            on="Time",
            direction="nearest",
        )

    circuit_info = None
    try:
        circuit_info = session.get_circuit_info()
    except Exception:
        circuit_info = None

    return telemetry, lap_obj, circuit_info

