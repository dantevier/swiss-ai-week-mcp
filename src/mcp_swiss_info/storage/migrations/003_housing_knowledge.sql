-- BWO/UFAB housing knowledge: one row per self-contained fact, language and revision.
-- Seeded by scripts/import_housing.py from data/housing_knowledge.json.
-- Timestamps are UTC ISO 8601 with Z; civil dates are YYYY-MM-DD.
-- Rates are integer basis points (125 = 1.25%).
CREATE TABLE IF NOT EXISTS housing_knowledge (
    id INTEGER PRIMARY KEY,
    item_key TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    record_kind TEXT NOT NULL CHECK (record_kind IN ('rate_publication', 'faq', 'guidance', 'jurisdiction')),
    topic TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('it', 'de', 'fr', 'rm')),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    source_passage TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(data_json)),
    conditions_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(conditions_json)),
    publisher TEXT NOT NULL DEFAULT 'BWO/UFAB',
    publisher_level TEXT NOT NULL DEFAULT 'federal',
    jurisdiction_level TEXT NOT NULL CHECK (jurisdiction_level IN ('federal', 'cantonal', 'municipal', 'mixed')),
    jurisdiction_code TEXT NOT NULL DEFAULT 'CH',
    source_kind TEXT NOT NULL CHECK (source_kind IN ('official_publication', 'official_explanation', 'official_guide')),
    source_url TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    source_version_date TEXT,
    published_on TEXT,
    effective_from TEXT,
    effective_to TEXT,
    applicability_verified INTEGER NOT NULL DEFAULT 0 CHECK (applicability_verified IN (0, 1)),
    scraped_at TEXT NOT NULL,
    last_verified_at TEXT NOT NULL,
    last_changed_at TEXT NOT NULL,
    refresh_interval_seconds INTEGER NOT NULL CHECK (refresh_interval_seconds > 0),
    next_check_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
    parser_version TEXT NOT NULL,
    UNIQUE (item_key, language, revision),
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from)
);

CREATE UNIQUE INDEX IF NOT EXISTS housing_current_unique
    ON housing_knowledge(item_key, language) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS housing_lookup
    ON housing_knowledge(topic, language, jurisdiction_code, effective_from)
    WHERE is_current = 1;
