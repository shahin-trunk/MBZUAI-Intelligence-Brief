# Prompt refactor fixtures

Saved production brief data, shaped as inputs and outputs for the
Ghostwriter A/B eval harness at
[`backend/evals/eval_ghostwriter_ab.py`](../../../evals/eval_ghostwriter_ab.py).

## Layout

```
prompt_refactor/
├── README.md   (this file)
└── ghostwriter/
    └── YYYY-MM-DD.json   (one fixture per production date)
```

## Fixture shape

Each `ghostwriter/{date}.json` is:

```json
{
  "date": "2026-04-NN",
  "gatekeeper_input": {
    "selected": [ /* one per card in that day's brief */ ],
    "allowed_ids": [ /* list of item IDs */ ]
  },
  "old_output": {
    "items": [ /* the real production Ghostwriter output for that day */ ]
  }
}
```

`gatekeeper_input` is shaped as the Ghostwriter expects —
see `prompts/ghostwriter_prompt.md` section "INPUT".

## Known caveat: synthetic `raw_content`

The real Ghostwriter pipeline feeds the prompt a `raw_content` field
containing the scout's collected article text — full paragraphs
extracted from source URLs. That raw text is **not persisted** after
the pipeline runs; only the Ghostwriter's **output** (headline,
key_bullets, analysis, etc.) lands in `briefs.raw_json` on Supabase.

These fixtures reconstruct `raw_content` from the production output —
concatenating the old `main_bullet` + `analysis` + `key_bullets`. This
is a deliberate compromise:

- **For a voice refactor** (shorter prompt, same facts, different
  phrasing) this is fine. The same synthetic input goes to both v1
  and v2, so the comparison isolates prose quality.
- **For a factual-fidelity refactor** (e.g., testing whether a new
  prompt hallucinates more) this is insufficient — you'd be measuring
  the model against its own prior output, not the true source.

If a future refactor needs fidelity evaluation, capture
`scout_output_{date}.json` intermediate artifacts from a live run and
save them alongside.

## Regeneration

```bash
cd backend
python -m evals.fetch_ghostwriter_fixtures \
    --dates 2026-04-06,2026-04-07,2026-04-08,2026-04-09,2026-04-13
```

Requires `NEXT_PUBLIC_SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in
the environment. See the script docstring for details.
