"""2026 health insurance premium MCP tool registration."""

from ..health_insurance import CSV_PATH, HealthInsurance
from ..server import mcp

health_insurance = HealthInsurance(csv_path=CSV_PATH)


@mcp.tool
def swiss_health_insurance_premiums(age: int, municipality_code: int, franchise: int) -> dict:
    """Look up 2026 Swiss basic health insurance minimum premiums.

    Premium reference: Priminfo (https://www.priminfo.admin.ch/de/praemien).
    Values were extracted from the KVG26 mapper into the local CSV, not fetched
    directly from Priminfo. Valid ONLY for 2026; INVALID for 2027 and later.
    age: completed years (19–25 young, 26+ adult); municipality_code: Swiss
    BFS municipality number, NOT a postal code/PLZ/CAP; franchise: annual
    deductible in CHF (300, 500, 1000, 1500, 2000 or 2500).
    Returns both with-accident and without-accident premium options.
    """
    return health_insurance.premiums(age, municipality_code, franchise)
