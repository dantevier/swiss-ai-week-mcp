"""Build the housing and driving licence SQLite data from data/ when the server starts."""

import importlib.util
from pathlib import Path

from .config.database_paths import driving_licence_path, housing_path
from .utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.local_databases")
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _import_rows(script: str, database: Path) -> None:
    spec = importlib.util.spec_from_file_location(script, SCRIPTS / f"{script}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.import_rows(database)


def build_local_databases() -> None:
    """Run both importers; a failure is logged and leaves the previous data in place.

    Imports are idempotent: unchanged rows are not duplicated, so running this on
    every start keeps the database in step with data/ after a pull.
    """
    for script, database in (
        ("import_housing", housing_path()),
        ("import_driving_licence", driving_licence_path()),
    ):
        try:
            _import_rows(script, database)
            logger.info(f"{script}: database ready at {database}")
        except Exception as error:  # the server must start even if one import fails
            logger.error(f"{script} failed; tools will use existing data if any: {error}")
