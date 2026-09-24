"""BAZG parcel-import MCP tool registration."""

import asyncio

from ..authority_pages import fetch_page
from ..customs import Customs
from ..server import mcp

customs = Customs(fetcher=fetch_page)


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
        customs.estimate_vat, goods_value_chf, shipping_chf, vat_rate, customs_duty_chf
    )
