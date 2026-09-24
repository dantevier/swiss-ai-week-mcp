-- Additive migration: keep the existing source rows and their stable IDs.
-- One fact represents one documented fee, deadline or requirement variant.
CREATE TABLE IF NOT EXISTS driving_licence_facts (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES driving_licence_sources(id) ON DELETE CASCADE,
    fact_key TEXT NOT NULL,
    fact_type TEXT NOT NULL CHECK (fact_type IN ('fee', 'deadline', 'requirement')),
    description_en TEXT NOT NULL,
    source_url TEXT NOT NULL,
    validated_at TEXT,
    origin TEXT NOT NULL DEFAULT 'seed' CHECK (origin IN ('seed', 'manual')),
    amount_min_rappen INTEGER,
    amount_max_rappen INTEGER,
    fee_code TEXT,
    fee_model TEXT CHECK (fee_model IN ('bundle', 'component')),
    period_value INTEGER,
    period_unit TEXT CHECK (period_unit IN ('days', 'months', 'years')),
    period_anchor TEXT,
    deadline_code TEXT,
    requirement_code TEXT,
    requirement_kind TEXT CHECK (requirement_kind IN ('document', 'exam', 'eligibility', 'submission', 'medical')),
    requirement_effect TEXT CHECK (requirement_effect IN ('required', 'waived', 'recommended', 'may_be_required')),
    UNIQUE (source_id, fact_key),
    CHECK (amount_min_rappen IS NULL OR amount_min_rappen >= 0),
    CHECK (amount_max_rappen IS NULL OR amount_max_rappen >= amount_min_rappen),
    CHECK (
        (fact_type = 'fee' AND amount_min_rappen IS NOT NULL AND amount_max_rappen IS NOT NULL
         AND fee_code IS NOT NULL AND fee_model IS NOT NULL
         AND period_value IS NULL AND requirement_code IS NULL)
        OR
        (fact_type = 'deadline' AND period_value IS NOT NULL AND period_value >= 0
         AND period_unit IS NOT NULL AND period_anchor IS NOT NULL AND deadline_code IS NOT NULL
         AND amount_min_rappen IS NULL AND requirement_code IS NULL)
        OR
        (fact_type = 'requirement' AND requirement_code IS NOT NULL
         AND requirement_kind IS NOT NULL AND requirement_effect IS NOT NULL
         AND amount_min_rappen IS NULL AND period_value IS NULL)
    )
);

-- Within a field, multiple values mean OR; across fields, conditions mean AND.
-- For example, category=A1 or B AND issuing_country=TW.
CREATE TABLE IF NOT EXISTS driving_licence_fact_conditions (
    fact_id INTEGER NOT NULL REFERENCES driving_licence_facts(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    operator TEXT NOT NULL CHECK (operator IN ('eq', 'gt', 'gte', 'lt', 'lte')),
    value TEXT NOT NULL,
    PRIMARY KEY (fact_id, field, operator, value)
);

CREATE INDEX IF NOT EXISTS idx_driving_licence_facts_source_type
    ON driving_licence_facts(source_id, fact_type);
CREATE INDEX IF NOT EXISTS idx_driving_licence_fact_conditions_lookup
    ON driving_licence_fact_conditions(field, operator, value);

-- Country membership used by conditional federal rules. Two-letter ISO codes.
CREATE TABLE IF NOT EXISTS driving_licence_country_groups (
    group_code TEXT NOT NULL,
    country_code TEXT NOT NULL CHECK (length(country_code) = 2),
    origin TEXT NOT NULL DEFAULT 'seed' CHECK (origin IN ('seed', 'manual')),
    PRIMARY KEY (group_code, country_code)
);

-- Query this view for one canton to receive both federal and local facts.
CREATE VIEW IF NOT EXISTS driving_licence_applicable_facts AS
SELECT requested.jurisdiction AS jurisdiction,
       source.jurisdiction AS rule_jurisdiction,
       fact.*
FROM driving_licence_sources AS requested
JOIN driving_licence_facts AS fact
JOIN driving_licence_sources AS source ON source.id = fact.source_id
WHERE source.jurisdiction = 'CH'
   OR source.jurisdiction = requested.jurisdiction;
