"""
Swiss tax tools for the mcp-swiss-info server.
"""

from ..server import mcp
from ..tax import KANTON_TAX_RATES, SwissTax

tax = SwissTax(rates=KANTON_TAX_RATES)


@mcp.tool
def compute_swiss_tax(kanton_shortcode: str) -> dict[str, float | int | str]:
    """Compute the tax rate for a Swiss canton."""
    return tax.compute(kanton_shortcode)
