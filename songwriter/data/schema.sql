PRAGMA foreign_keys = ON;

CREATE TABLE words (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  word                  TEXT NOT NULL,
  language              TEXT NOT NULL DEFAULT 'en',
  ipa                   TEXT,
  arpabet               TEXT,
  syllables             INTEGER,
  stress_pattern        TEXT,
  rhyme_class           TEXT,
  vowel_shape           TEXT,
  first_syllable_attack TEXT,
  consonant_density     REAL,
  syllable_count_class  TEXT,
  UNIQUE(word, language)
);
CREATE INDEX idx_words_word ON words(word);
CREATE INDEX idx_words_rhyme_class ON words(rhyme_class);
CREATE INDEX idx_words_vowel_shape ON words(vowel_shape);

CREATE TABLE genres (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  parent_genre_id     INTEGER REFERENCES genres(id),
  description         TEXT,
  typical_bpm_min     INTEGER,
  typical_bpm_max     INTEGER,
  default_structure_id INTEGER,
  notes_for_suno      TEXT
);

CREATE TABLE sub_genres (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  genre_id            INTEGER NOT NULL REFERENCES genres(id),
  slug                TEXT NOT NULL,
  name                TEXT NOT NULL,
  description         TEXT,
  typical_bpm_min     INTEGER,
  typical_bpm_max     INTEGER,
  default_structure_id INTEGER,
  notes_for_suno      TEXT,
  UNIQUE(genre_id, slug)
);
CREATE INDEX idx_sub_genres_genre ON sub_genres(genre_id);

CREATE TABLE vocab_banks (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  slug            TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  description     TEXT,
  parent_bank_id  INTEGER REFERENCES vocab_banks(id)
);

CREATE TABLE vocab_bank_words (
  bank_id           INTEGER NOT NULL REFERENCES vocab_banks(id),
  word_id           INTEGER NOT NULL REFERENCES words(id),
  emotional_weight  REAL,
  imagery_class     TEXT,
  cliche_flag       INTEGER NOT NULL DEFAULT 0,
  ai_bias_flag      INTEGER NOT NULL DEFAULT 0,
  notes             TEXT,
  PRIMARY KEY (bank_id, word_id)
);

CREATE TABLE cadence_patterns (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  syllable_template   TEXT,
  stress_template     TEXT,
  typical_genres      TEXT,
  example_lines       TEXT,
  rhyme_compatibility TEXT
);

CREATE TABLE songwriter_profiles (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                  TEXT UNIQUE NOT NULL,
  display_name          TEXT NOT NULL,
  real_name             TEXT,
  era                   TEXT,
  primary_genre_id      INTEGER REFERENCES genres(id),
  role                  TEXT NOT NULL CHECK (role IN
                          ('pure-songwriter','producer-songwriter','singer-songwriter','self-writing-artist')),
  sub_genres            TEXT,
  notable_credits       TEXT,
  craft_signature       TEXT,
  personality_traits    TEXT,
  writing_style         TEXT,
  preferred_cadences    TEXT,
  vocab_fingerprint     TEXT,
  phonetic_fingerprint  TEXT,
  structure_preferences TEXT,
  hook_style            TEXT,
  reference_tracks      TEXT,
  adoption_prompt       TEXT NOT NULL
);

CREATE TABLE artist_descriptor_cache (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  normalized_name   TEXT UNIQUE NOT NULL,
  canonical_name    TEXT NOT NULL,
  era_label         TEXT,
  descriptor        TEXT NOT NULL,
  descriptor_short  TEXT NOT NULL,
  descriptor_long   TEXT NOT NULL,
  vocal_attributes  TEXT,
  production_attrs  TEXT,
  genre_context     TEXT,
  source            TEXT NOT NULL CHECK (source IN
                      ('auto-llm','songwriter-profile-derived','user-curated')),
  quality_state     TEXT NOT NULL DEFAULT 'unverified'
                      CHECK (quality_state IN ('unverified','reviewed','pinned')),
  use_count         INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at      TEXT
);

CREATE TABLE suno_burn_list (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  word          TEXT UNIQUE NOT NULL,
  severity      TEXT NOT NULL CHECK (severity IN ('mild','strong','extreme')),
  drift_direction TEXT,
  alternatives  TEXT
);

CREATE TABLE structure_templates (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  slug                TEXT UNIQUE NOT NULL,
  name                TEXT NOT NULL,
  sections            TEXT NOT NULL,
  genre_compatibility TEXT
);

CREATE TABLE emotion_tempo_map (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  emotion       TEXT NOT NULL,
  sub_genre_id  INTEGER NOT NULL REFERENCES sub_genres(id),
  bpm_min       INTEGER NOT NULL,
  bpm_max       INTEGER NOT NULL,
  energy_curve  TEXT,
  anti_prompts  TEXT,
  UNIQUE(emotion, sub_genre_id)
);

CREATE TABLE production_fingerprints (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  sub_genre_id          INTEGER UNIQUE NOT NULL REFERENCES sub_genres(id),
  instrumentation       TEXT,
  vocal_style           TEXT,
  mix_attributes        TEXT,
  positive_descriptors  TEXT,
  negative_descriptors  TEXT
);
