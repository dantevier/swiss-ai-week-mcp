"""BWO/UFAB housing MCP tool registration."""

from ..config.database_paths import housing_path
from ..housing import Housing, Language
from ..server import mcp

housing = Housing(database_path=housing_path)


@mcp.tool
def swiss_reference_interest_rate(as_of: str | None = None, language: Language = "it") -> dict:
    """Return the Swiss mortgage reference interest rate for rents (BWO/UFAB).

    Call this tool first, before search_knowledge, for the reference rate
    (Referenzzinssatz, taux de référence, tasso di riferimento).
    National value, valid in all cantons: never ask for a canton. as_of is an
    ISO date (YYYY-MM-DD, default today); the publication in force on that
    date is chosen by its effective date. Dates before the imported coverage,
    or after the announced next publication, are not answered: the history is
    not imported and future values are not forecast. language (it, de, fr, rm)
    selects the source passage; without a verified source in that language
    the Italian publication is returned and labelled. Rates are also given in
    basis points (125 = 1.25%). Rent changes are not calculated here.
    """
    return housing.reference_interest_rate(as_of, language)


@mcp.tool
def swiss_housing_info(
    question: str | None = None,
    language: Language = "it",
    topic: str | None = None,
    limit: int = 5,
) -> dict:
    """Find official BWO/UFAB guidance on Swiss residential renting.

    Call this tool first for any Swiss residential renting question (Mietrecht,
    bail à loyer, locazione, locaziun), before search_knowledge: rent deposit
    (Kaution, caution, cauzione), termination, rent increase or reduction,
    ancillary costs, defects, move-in/move-out reports. Answer from the
    returned passages; do not add articles or amounts they do not contain.
    Covers: reference-rate method and rent adjustment FAQ (increase, reduction,
    contesting, exceptions), federal vs cantonal competence, and the "Abitare
    in Svizzera" guide on deposit, move-in/move-out reports, ancillary costs,
    defects, alterations and termination. Topics: reference_rate,
    rent_adjustment, jurisdiction, deposit, handover, utilities, defects,
    alterations, termination. Use swiss_reference_interest_rate for the
    current rate value. Rules are national: do not ask for a canton.
    Not covered: cantonal initial-rent forms, conciliation authority
    addresses, individual rent calculations, commercial leases, purchases.
    Each result carries the verbatim source passage, URL, locator, source
    language and conditions; check the conditions before applying a result.
    limit: 1-10.
    """
    return housing.info(question, language, topic, limit)
