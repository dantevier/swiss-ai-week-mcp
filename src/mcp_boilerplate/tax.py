"""Legacy demonstrator for a static cantonal tax lookup."""

from collections.abc import Mapping

KANTON_TAX_RATES: dict[str, dict[str, float | int | str]] = {
    "ZH": {"kanton": "Zurich", "tax_rate": 0.20, "tax_percentage": 20},
    "BE": {"kanton": "Bern", "tax_rate": 0.25, "tax_percentage": 25},
}


class SwissTax:
    """Demonstration lookup with injectable rates; not an official tax assessment."""

    def __init__(self, rates: Mapping[str, dict[str, float | int | str]]):
        self.rates = rates

    def compute(self, kanton_shortcode: str) -> dict[str, float | int | str]:
        normalized = (kanton_shortcode or "").strip().upper()
        selected = self.rates.get(normalized)
        if selected is None:
            selected = {"kanton": "Other", "tax_rate": 0.10, "tax_percentage": 10}
        return {
            "kanton_shortcode": normalized,
            "kanton": selected["kanton"],
            "tax_rate": selected["tax_rate"],
            "tax_percentage": selected["tax_percentage"],
        }
