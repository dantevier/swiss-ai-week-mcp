"""
Swiss tax tools for the MCP Boilerplate server.
"""

from ..server import mcp
from ..utils.logger import setup_logger

logger = setup_logger("mcp_boilerplate.tools.tax")


_KANTON_TAX_RATES: dict[str, dict[str, float | int | str]] = {
    "ZH": {"kanton": "Zurich", "tax_rate": 0.20, "tax_percentage": 20},
    "BE": {"kanton": "Bern", "tax_rate": 0.25, "tax_percentage": 25},
}


@mcp.tool
def compute_swiss_tax(kanton_shortcode: str) -> dict[str, float | int | str]:
    """Compute the tax rate for a Swiss canton."""
    try:
        normalized = (kanton_shortcode or "").strip().upper()
        selected = _KANTON_TAX_RATES.get(normalized)

        if selected is None:
            selected = {"kanton": "Other", "tax_rate": 0.10, "tax_percentage": 10}

        result = {
            "kanton_shortcode": normalized,
            "kanton": selected["kanton"],
            "tax_rate": selected["tax_rate"],
            "tax_percentage": selected["tax_percentage"],
        }

        logger.debug(f"Swiss tax lookup for {normalized}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in compute_swiss_tax tool: {e}")
        raise
