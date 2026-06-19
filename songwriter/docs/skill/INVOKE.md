# Using the Songwriter Skill

The skill is a Claude Code slash command + skill bundle that drives the songwriting workflow.

## One-time setup

```bash
cd /path/to/songwriter
./.venv/bin/songwriter-build              # if data/songwriter.db is missing
./start.sh                                 # boots the API on :8000
```

In a separate terminal, open Claude Code from the repo root:

```bash
cd /path/to/songwriter
claude
```

## Commands

```
/song                           # menu
/song new                       # 6-step wizard → creates a new song JSON
/song open <slug>               # load a song and show status
/song list                      # list songs in ~/Songwriter/songs/

/song draft [section]           # draft section(s) with the 7-step framework
/song refine <section>          # conversational refinement
/song alt <section> <line>      # 3 alternatives for one line
/song validate                  # run all 5 rules + present results

/song lens <slug>               # apply or change songwriter lens
/song prompt                    # 5-phase Suno prompt refinement loop
/song prompt --improve "<existing prompt>"
/song export                    # final cleanup + Suno prompt + save
```

## Files the skill touches

- `~/Songwriter/songs/<slug>.json` — your song state. Edit by hand if you want; the file watcher will sync.
- `localhost:8000` — the API. Verify with `curl -sf http://localhost:8000/healthz`.

## When something doesn't work

- "API not running" → run `./start.sh` from the repo root.
- "Song not found" → check `~/Songwriter/songs/<slug>.json` exists. If it does, the slug in your command may be off.
- "Validation always fails" → `curl -sX POST 'http://localhost:8000/songs/<slug>/validate?include_llm=false' | jq` to see the raw output. The skill should be doing this for you, but it's the same data.
- "I think the skill is hallucinating" → it shouldn't reach for training-data details when the API is reachable. If it does, mention "use the API" and it will reset.

## Files at a glance

```
songwriter/.claude/
├── commands/
│   └── song.md                # the /song slash command
└── skills/
    └── songwriting/
        ├── SKILL.md           # main skill
        └── reference/         # workflow, lens, descriptor, prompt, constraints, API recipes
```
