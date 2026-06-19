"""Top-level build orchestrator. Run via `songwriter-build` or `python -m songwriter.seeds.build`."""

import argparse
import time
from pathlib import Path

from songwriter.seeds import (
    DATA_DIR, CACHE_DIR, DB_PATH,
    cmudict, db as db_module,
)
from songwriter.seeds.seeders import (
    words as words_seeder,
    genres as genres_seeder,
    cadence_patterns as cadence_seeder,
    structure_templates as struct_seeder,
    production_fingerprints as prod_seeder,
    emotion_tempo_map as et_seeder,
    burn_list as burn_seeder,
    vocab_banks as vocab_seeder,
    songwriter_profiles as sw_seeder,
    sonic_descriptors as desc_seeder,
)


def _step(label: str, fn) -> None:
    t0 = time.time()
    fn()
    dt = time.time() - t0
    print(f"  {label:<32}  {dt:6.2f}s")


def run(*, db_path: Path | None = None, cache_dir: Path | None = None) -> None:
    db_path = db_path or DB_PATH
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cmudict_path = cache_dir / "cmudict.dict"

    print(f"Building {db_path} ...")
    print("STEP                              TIME")
    print("-" * 42)

    _step("init_db", lambda: db_module.init_db(db_path))
    _step("download_cmudict", lambda: cmudict.download(cmudict_path))
    _step("seed_words", lambda: words_seeder.seed_from_cmudict(db_path, cmudict_path))
    _step("seed_genres", lambda: genres_seeder.seed(db_path, DATA_DIR / "genres.yml"))
    _step("seed_cadence", lambda: cadence_seeder.seed(db_path, DATA_DIR / "cadence_patterns.yml"))
    _step("seed_structure", lambda: struct_seeder.seed(db_path, DATA_DIR / "structure_templates.yml"))
    _step("seed_production", lambda: prod_seeder.seed(db_path, DATA_DIR / "production_fingerprints.yml"))
    _step("seed_emotion_tempo", lambda: et_seeder.seed(db_path, DATA_DIR / "emotion_tempo_map.yml"))
    _step("seed_burn_list", lambda: burn_seeder.seed(db_path, DATA_DIR / "burn_list.yml"))
    _step("seed_vocab", lambda: vocab_seeder.seed_directory(db_path, DATA_DIR / "vocab"))
    _step("seed_songwriters", lambda: sw_seeder.seed_directory(db_path, DATA_DIR / "songwriters"))
    _step("seed_descriptors", lambda: desc_seeder.seed(db_path, DATA_DIR / "descriptors" / "seeded.yml"))

    print(f"\nBuild complete: {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build songwriter.db")
    parser.add_argument("--db", type=Path, default=None, help="Override DB output path")
    parser.add_argument("--cache", type=Path, default=None, help="Override CMUdict cache dir")
    args = parser.parse_args()
    run(db_path=args.db, cache_dir=args.cache)


if __name__ == "__main__":
    main()
