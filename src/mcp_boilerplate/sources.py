"""Reviewed Swiss authorities: the registry of every source the server reads.

``SOURCES`` maps each authority level to its named ``Source`` rows. It lists the pages
the crawler fetches, validates and saves, and the three commercial-register API
endpoints that company_info calls live. The API rows are listed for review and
attribution; their ``expected`` text is ``NOT_A_PAGE``, so they fail crawl validation
by construction and nothing is saved for them.

``API_SOURCES`` is the companion table the three API rows are built from: base URL,
authority, the hosts for the egress allow-list (``api_hosts()``) and the terms of use.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    url: str
    authority: str
    expected: str


@dataclass(frozen=True)
class ApiSource:
    base_url: str
    hosts: tuple[str, ...]
    authority: str
    terms: str


API_SOURCES: dict[str, ApiSource] = {
    "zefix_lindas": ApiSource(
        "https://lindas.admin.ch/query",
        ("lindas.admin.ch", "register.ld.admin.ch"),
        "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
        "LINDAS: open use, provide the source. Not legally binding.",
    ),
    "zefix_web": ApiSource(
        "https://www.zefix.admin.ch/ZefixREST/api/v1",
        ("www.zefix.admin.ch",),
        "Eidgenössisches Amt für das Handelsregister (EHRA), Bundesamt für Justiz",
        "Undocumented web endpoint; called only when RESPECT_ROBOTS_TXT=false or credentials are set.",
    ),
    "gazette": ApiSource(
        "https://amtsblattportal.ch/api/v1",
        ("amtsblattportal.ch",),
        "Schweizerisches Handelsamtsblatt (SHAB), SECO",
        "The signed PDF is the binding version.",
    ),
}


def api_hosts() -> frozenset[str]:
    """Union of every host any registered API source (or its redirects) may reach."""
    return frozenset(host for source in API_SOURCES.values() for host in source.hosts)


# The API rows in SOURCES are live endpoints that company_info calls. The crawler validates
# ``expected`` against fetched text, so a full federal refresh fails and saves nothing for them.
NOT_A_PAGE = "\x00not-a-page"


SOURCES: dict[str, dict[str, Source]] = {
    "federal": {
        "zefix_lindas": Source(
            API_SOURCES["zefix_lindas"].base_url, API_SOURCES["zefix_lindas"].authority, NOT_A_PAGE
        ),
        "zefix_web": Source(
            API_SOURCES["zefix_web"].base_url, API_SOURCES["zefix_web"].authority, NOT_A_PAGE
        ),
        "gazette": Source(
            API_SOURCES["gazette"].base_url, API_SOURCES["gazette"].authority, NOT_A_PAGE
        ),
        "health_insurance_premiums": Source(
            "https://ckan.opendata.swiss/api/3/action/package_show?id=health-insurance-premiums",
            "Federal Office of Public Health (BAG)",
            "Archiv_Praemien_2026.zip",
        ),
        "premium_regions_2026": Source(
            "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2022/184/"
            "20260101/de/html/fedlex-data-admin-ch-eli-cc-2022-184-20260101-de-html.html",
            "Federal Department of Home Affairs (FDHA)",
            "Prämienregionen",
        ),
        "reference_interest_rate": Source(
            "https://www.bwo.admin.ch/de/referenzzinssatz",
            "Federal Office for Housing (BWO)",
            "Hypothekarischer Referenzzinssatz",
        ),
        "reference_interest_rate_law": Source(
            "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/"
            "1990/835_835_835/20251001/de/html/"
            "fedlex-data-admin-ch-eli-cc-1990-835_835_835-20251001-de-html.html",
            "Swiss Confederation (Fedlex)",
            "Verordnung über die Miete und Pacht",
        ),
        "foreign_driving_licence_law": Source(
            "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/"
            "1976/2423_2423_2423/20260101/de/html/"
            "fedlex-data-admin-ch-eli-cc-1976-2423_2423_2423-20260101-de-html.html",
            "Swiss Confederation (Fedlex)",
            "Verkehrszulassungsverordnung",
        ),
    },
    "cantonal": {
        "gr_school_holidays_2026_27": Source(
            "https://www.gr.ch/DE/institutionen/verwaltung/ekud/avs/Volksschule/"
            "SB_Ferienplaene_2026_2027_de.pdf",
            "Canton of Graubünden",
            "Schul- und Ferienplan",
        ),
        "vd_school_holidays_2023_31": Source(
            "https://www.vd.ch/fileadmin/user_upload/themes/formation/Vacances_scolaires/"
            "def_calendrier_vacances_scolaires_2023_2031.pdf",
            "Canton of Vaud",
            "Vacances scolaires vaudoises",
        ),
        "ti_school_holidays_2026_27": Source(
            "https://www4.ti.ch/fileadmin/DECS/calendario_scolastico/"
            "Calendario_scolastico_2026_2027.pdf",
            "Canton of Ticino",
            "vacanze",
        ),
        "zh_school_holidays": Source(
            "https://www.zh.ch/de/bildung/bildungssystem/schulferien.html",
            "Canton of Zürich",
            "Schulferien",
        ),
    },
    "municipal": {
        "scuol_waste": Source(
            "https://www.regiunebvm.ch/de/kehricht/",
            "Region Engiadina Bassa / Val Müstair",
            "Kehricht",
        ),
        "bern_arrival": Source(
            "https://www.bern.ch/themen/zuzug-umzug-wegzug/",
            "City of Bern",
            "Zuzug, Umzug und Wegzug",
        ),
        "st_gallen_school_holidays": Source(
            "https://www.stadt.sg.ch/home/schule-bildung/Schulferien.html",
            "City of St. Gallen",
            "Schuljahr",
        ),
        "lausanne_arrival": Source(
            "https://www.lausanne.ch/dam/jcr%3A379afd27-3817-4a2f-ab48-6d64f06ead2a/"
            "Brochure_Contr%C3%B4le_Habitants.pdf",
            "City of Lausanne",
            "Contrôle des habitants de Lausanne",
        ),
    },
}
