"""Conservative parcel-import VAT estimate based on live BAZG rules."""

import asyncio
import math
import re
from decimal import ROUND_HALF_UP, Decimal
from urllib.error import HTTPError, URLError

from ..server import mcp
from ._authority_pages import fetch_page, paragraph
from ._public_api import unavailable

SOURCE_URL = "https://www.bazg.admin.ch/en/receipt-of-letters-and-parcels"
RATES = {"standard": Decimal("0.081"), "reduced": Decimal("0.026")}


def _estimate(
    goods_value_chf: float, shipping_chf: float, vat_rate: str, customs_duty_chf: float | None
) -> dict:
    if vat_rate not in RATES or any(
        not math.isfinite(value) or value < 0 or value > 100_000_000
        for value in (
            goods_value_chf,
            shipping_chf,
            *([customs_duty_chf] if customs_duty_chf is not None else []),
        )
    ):
        return {
            "status": "invalid_input",
            "message": "Use non-negative CHF amounts and vat_rate standard or reduced.",
        }
    try:
        page = fetch_page(SOURCE_URL, "Receipt of letters and parcels")
        rate_rule = paragraph(page, "Value added tax amounts to", "2.6 %")
        threshold_rule = paragraph(page, "CHF 62", "CHF 193")
        basis_rule = paragraph(page, "All costs up to the destination", "import duties")
        if not re.search(r"8[,.]1\s*%", rate_rule) or not re.search(r"2[,.]6\s*%", rate_rule):
            raise ValueError("Published VAT rates changed")
        if not re.search(r"up to 5 Swiss francs", threshold_rule, re.I):
            raise ValueError("Published VAT collection threshold changed")
        rate = RATES[vat_rate]
        base = Decimal(str(goods_value_chf)) + Decimal(str(shipping_chf))
        if customs_duty_chf is not None:
            base += Decimal(str(customs_duty_chf))
        estimate = (base * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # The website quotes approximate CHF 62/193 bases; do not turn
        # rounding close to CHF 5 into a categorical customs decision.
        return {
            "status": "answered",
            "vat_rate": vat_rate,
            "rate_percent": float(rate * 100),
            "assessment_basis_chf": float(base),
            "estimated_vat_chf": float(estimate),
            "customs_duty_included": customs_duty_chf is not None,
            "collection_guidance": (
                "Customs duty not supplied: VAT assessment and collection may change when duty is added."
                if customs_duty_chf is None
                else "BAZG does not levy import VAT up to CHF 5; this is an estimate, not an assessment."
            ),
            "carrier_clearance_fee_chf": None,
            "source_evidence": [rate_rule, threshold_rule, basis_rule],
            "source_url": page["source_url"],
            "fetched_at_utc": page["fetched_at_utc"],
            "note": "For postal/courier purchases only. Goods value excludes separately shown foreign VAT; shipping to Switzerland and any import duty are part of the VAT basis. Customs duties, other taxes and carrier fees depend on the goods and carrier and are not computed here.",
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        return unavailable(exc)


@mcp.tool
async def swiss_import_parcel_vat(
    goods_value_chf: float,
    shipping_chf: float = 0,
    vat_rate: str = "standard",
    customs_duty_chf: float | None = None,
) -> dict:
    """Estimate import VAT for an online purchase shipped to Switzerland.

    CHF purchase price excludes foreign VAT separately shown on the invoice.
    Add shipping to Switzerland and, if known, customs duty. Standard goods
    are 8.1%, reduced-rate eligible goods 2.6%. Does not calculate customs
    tariffs or courier fees, or apply the private-person gift exemption.
    Official source: https://www.bazg.admin.ch/en/receipt-of-letters-and-parcels
    """
    return await asyncio.to_thread(
        _estimate, goods_value_chf, shipping_chf, vat_rate, customs_duty_chf
    )
