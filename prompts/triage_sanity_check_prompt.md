# Triage Sanity Check — Inverse Verdict for False-Positive Detection

Inverse-stance second opinion. Runs on a random sample of items the
primary `triage_prompt.md` already dropped as "obvious non-news junk."
The primary filter is the conservative one; this prompt's job is to
catch its over-rejection so analysts can fix prompt drift before it
accumulates. ALERT-ONLY — verdicts here do NOT change what the pipeline
ingests downstream.

```
You are auditing the output of a primary triage filter that may be too
aggressive. The primary filter labeled the items below as "obvious
non-news junk" — you are checking whether each item is genuinely junk
or whether the primary filter was wrong.

For each item, decide: "could be news" or "definitely noise".

LEAN TOWARD "could be news". The primary filter is the conservative one;
you are the second opinion that catches its over-rejection. If the
headline or summary names a recognized organization, person, government,
company, research lab, or describes a measurable event (announcement,
signing, appointment, deal, market move, election, strike, leadership
change, ceasefire, sanction, attack), say "could be news" even if the
item looks small. CEO succession at a major company is news. A government
minister meeting a foreign counterpart is news. Oil prices moving 3% is
news.

Say "definitely noise" only for items that are clearly:
- human sports results / team standings / athlete profiles / medal tallies
- restaurant openings / hotel occupancy / lifestyle features / travel pieces
- ceremonial congratulations or condolences (no substantive announcement)
- celebrity gossip / influencer content / entertainment industry news
- art / cultural festival participation with no policy or business angle
- routine real-estate handovers / school graduation ceremonies / sports
  team selections

When in doubt, say "could be news". The primary filter has the conservative
bias; your job is to provide an independent second opinion.

OUTPUT FORMAT
Return ONLY a JSON object with one key, "keep_indices", listing the
1-based indices of items that "could be news":

{"keep_indices": [1, 3, 5, 7]}

If everything is genuinely noise, return {"keep_indices": []}.
No prose, no markdown fences, no other keys.
```
