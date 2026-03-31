from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastf1.ergast import Ergast


@lru_cache(maxsize=32)
def get_driver_standings(season: int, round_num: int | None = None) -> pd.DataFrame:
    ergast = Ergast()
    res = ergast.get_driver_standings(season=season, round=round_num)
    if not res.content:
        return pd.DataFrame()
    return res.content[0].copy()


@lru_cache(maxsize=32)
def get_constructor_standings(season: int, round_num: int | None = None) -> pd.DataFrame:
    ergast = Ergast()
    res = ergast.get_constructor_standings(season=season, round=round_num)
    if not res.content:
        return pd.DataFrame()
    return res.content[0].copy()


def build_standings_timeseries(*, season: int, rounds: list[int], kind: str, top_n: int = 10) -> pd.DataFrame:
    """
    Returns long dataframe with columns: round, name, position, points
    kind: 'driver' | 'constructor'
    """
    rows: list[dict] = []
    if kind not in {"driver", "constructor"}:
        raise ValueError("kind must be 'driver' or 'constructor'")

    for rnd in rounds:
        df = get_driver_standings(season, rnd) if kind == "driver" else get_constructor_standings(season, rnd)
        if df is None or df.empty:
            continue

        if kind == "driver":
            df = df.copy()
            df["name"] = (df["givenName"].astype(str).str.strip() + " " + df["familyName"].astype(str).str.strip()).str.strip()
        else:
            df = df.copy()
            df["name"] = df["constructorNames"].apply(lambda x: x[0] if isinstance(x, list) and x else str(x))

        df["position_num"] = pd.to_numeric(df["position"], errors="coerce")
        df["points_num"] = pd.to_numeric(df["points"], errors="coerce")

        df = df.sort_values("position_num").head(top_n)
        for _, r in df.iterrows():
            rows.append(
                {
                    "round": int(rnd),
                    "name": str(r.get("name", "")),
                    "position": float(r.get("position_num")) if pd.notna(r.get("position_num")) else None,
                    "points": float(r.get("points_num")) if pd.notna(r.get("points_num")) else None,
                }
            )

    return pd.DataFrame(rows)

