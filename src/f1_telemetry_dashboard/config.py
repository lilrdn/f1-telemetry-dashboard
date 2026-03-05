from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


@dataclass(frozen=True)
class Settings:
    port: int
    cache_dir: Path
    portrait_dir: Path
    team_logo_dir: Path


def load_settings(project_root: Path | None = None) -> Settings:
    root = project_root or Path.cwd()

    port = int(_env("F1_PORT", "8051") or "8051")
    cache_dir = Path(_env("F1_CACHE_DIR", str(root / "f1_cache")) or str(root / "f1_cache"))
    portrait_dir = Path(_env("F1_PORTRAIT_DIR", str(root / "data" / "portraits")) or str(root / "data" / "portraits"))
    team_logo_dir = Path(_env("F1_TEAM_LOGO_DIR", str(root / "data" / "teams")) or str(root / "data" / "teams"))

    return Settings(
        port=port,
        cache_dir=cache_dir,
        portrait_dir=portrait_dir,
        team_logo_dir=team_logo_dir,
    )


TEAM_LOGO_MAP: dict[str, str] = {
    "Ferrari": "ferrari",
    "Alpine": "alpine",
    "Haas F1 Team": "haas",
    "Kick Sauber": "kick_sauber",
    "McLaren": "mclaren",
    "Mercedes": "mercedes",
    "Red Bull Racing": "red_bull",
    # RB / Racing Bulls naming variants
    "RB": "visa_cash_app_rb",
    "Visa Cash App RB": "visa_cash_app_rb",
    "Racing Bulls": "visa_cash_app_rb",
    "Racing Bulls F1 Team": "visa_cash_app_rb",
    # Misc future/alt labels (safe no-op if file absent)
    "Audi": "audi",
    "Cadillac": "cadillac",
    "Williams": "williams",
    "Aston Martin": "aston_martin",
    "Aston Martin Aramco": "aston_martin",
}


DRIVER_DB: dict[str, dict[str, str]] = {
    "VER": {"name": "Max Verstappen", "team": "Red Bull Racing"},
    "HAM": {"name": "Lewis Hamilton", "team": "Mercedes"},
    "LEC": {"name": "Charles Leclerc", "team": "Ferrari"},
    "PER": {"name": "Sergio Perez", "team": "Red Bull Racing"},
    "SAI": {"name": "Carlos Sainz", "team": "Ferrari"},
    "NOR": {"name": "Lando Norris", "team": "McLaren"},
    "PIA": {"name": "Oscar Piastri", "team": "McLaren"},
    "RUS": {"name": "George Russell", "team": "Mercedes"},
    "ALO": {"name": "Fernando Alonso", "team": "Aston Martin"},
    "STR": {"name": "Lance Stroll", "team": "Aston Martin"},
}

