-- One row per coverage entry in data/driving_licence/driving_licence.toml.
-- English research notes are imported from data/driving_licence/driving_licence.en.toml.
-- Structured variants are added by migration 002_driving_licence_facts.sql.
CREATE TABLE IF NOT EXISTS driving_licence_sources (
    id INTEGER PRIMARY KEY,
    jurisdiction TEXT NOT NULL,
    subtopic TEXT NOT NULL,
    resolution_level TEXT NOT NULL,
    on_missing_place TEXT NOT NULL,
    authority TEXT NOT NULL,
    authority_level TEXT NOT NULL,
    source_url TEXT NOT NULL,
    landing_url TEXT,
    source_status TEXT NOT NULL,
    validated_at TEXT,
    legal_basis TEXT,
    notes TEXT NOT NULL,
    UNIQUE (jurisdiction, subtopic)
);
