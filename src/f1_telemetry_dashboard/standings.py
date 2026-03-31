from __future__ import annotations

from functools import lru_cache
import time

import pandas as pd
from fastf1.ergast import Ergast


def _ergast_call_with_retries(func, *, retries: int = 2, base_sleep_s: float = 0.75):
    """
    Ergast endpoint sometimes times out (FastF1 uses a short read timeout).
    We retry a couple of times and let callers degrade gracefully.
    """
    last_exc: Exception | None = None
    for i in range(retries + 1):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if i >= retries:
                break
            time.sleep(base_sleep_s * (2**i))
    raise last_exc  # type: ignore[misc]


@lru_cache(maxsize=32)
def get_driver_standings(season: int, round_num: int | None = None) -> pd.DataFrame:
    ergast = Ergast()
    try:
        res = _ergast_call_with_retries(lambda: ergast.get_driver_standings(season=season, round=round_num))
        if not res.content:
            return pd.DataFrame()
        return res.content[0].copy()
    except Exception:
        return pd.DataFrame()


@lru_cache(maxsize=32)
def get_constructor_standings(season: int, round_num: int | None = None) -> pd.DataFrame:
    ergast = Ergast()
    try:
        res = _ergast_call_with_retries(lambda: ergast.get_constructor_standings(season=season, round=round_num))
        if not res.content:
            return pd.DataFrame()
        return res.content[0].copy()
    except Exception:
        return pd.DataFrame()


def build_standings_timeseries(*, season: int, rounds: list[int], kind: str, top_n: int | None = 10) -> pd.DataFrame:
    """
    Returns long dataframe with columns: round, name, position, points
    kind: 'driver' | 'constructor'
    """
    rows: list[dict] = []
    if kind not in {"driver", "constructor"}:
        raise ValueError("kind must be 'driver' or 'constructor'")

    # Limit the amount of live requests to avoid blocking the UI.
    rounds = list(rounds)[:30]
    for rnd in rounds:
        df = get_driver_standings(season, rnd) if kind == "driver" else get_constructor_standings(season, rnd)
        if df is None or df.empty:
            continue

        if kind == "driver":
            df = df.copy()
            df["name"] = (df["givenName"].astype(str).str.strip() + " " + df["familyName"].astype(str).str.strip()).str.strip()
        else:
            df = df.copy()
            # fastf1 ergast constructor standings uses 'constructorName' (string)
            if "constructorName" in df.columns:
                df["name"] = df["constructorName"].astype(str).str.strip()
            elif "constructorNames" in df.columns:
                # fallback for any older/alternative schema
                df["name"] = df["constructorNames"].apply(lambda x: x[0] if isinstance(x, list) and x else str(x))
            else:
                df["name"] = ""

        df["position_num"] = pd.to_numeric(df["position"], errors="coerce")
        df["points_num"] = pd.to_numeric(df["points"], errors="coerce")

        df = df.sort_values("position_num")
        if top_n is not None:
            df = df.head(top_n)
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

