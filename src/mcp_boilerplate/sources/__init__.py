"""Upstream data sources for Swiss company data.

lindas   - Zefix graph on LINDAS (primary, keyless, official)
zefix    - Zefix REST enrichment (status, SHAB date, cantonal excerpt link)
gazette  - Amtsblattportal (SHAB + cantonal gazettes), UID-scoped publications
http     - shared httpx client with egress allow-list

Parts of this package are vendored from malkreide/register-mcp (MIT).
See LICENSE-register-mcp in this directory.
"""
