"""Foreign driving-licence exchange MCP tool registration."""

from ..config.database_paths import driving_licence_path
from ..driving_licence import DrivingLicence, FactType
from ..server import mcp

driving_licence = DrivingLicence(database_path=driving_licence_path)


@mcp.tool
def get_driving_licence_exchange_info(canton: str = "CH", fact_type: FactType = "all") -> dict:
    """Look up official-source facts about exchanging a foreign driving licence in Switzerland.

    Call this tool first, before search_knowledge, for any foreign driving
    licence exchange question: control drive (Kontrollfahrt, course de
    contrôle, corsa di controllo), country exemptions (ASTRA country lists,
    e.g. Taiwan only for categories A1 and B), fees, deadlines, documents.
    Use canton "CH" when no canton is given.
    Call this tool for Swiss driving licence exchange questions about fees,
    deadlines, required documents, exams or eligibility. Use a two-letter
    canton code (for example GR, ZH or VD); CH returns federal rules only.
    fact_type can narrow the result to fee, deadline or requirement.

    Every result includes its authority, source URL, validation date and
    applicability conditions. Conditions are supplied as documented: the
    caller must check them against the person's circumstances before treating
    a conditional fact as applicable. A missing fact does not mean that a fee
    is zero or that a requirement is waived.
    """
    return driving_licence.exchange_info(canton, fact_type)
