"""Shared configured locations for imported SQLite databases."""

from pathlib import Path

from .settings import settings

DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / "var" / "swissproject.sqlite3"


def housing_path() -> Path:
    return (
        Path(settings.housing_db_path).expanduser()
        if settings.housing_db_path
        else DEFAULT_DATABASE
    )


def driving_licence_path() -> Path:
    return (
        Path(settings.driving_licence_db_path).expanduser()
        if settings.driving_licence_db_path
        else DEFAULT_DATABASE
    )
