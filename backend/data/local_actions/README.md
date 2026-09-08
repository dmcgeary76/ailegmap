# Local actions

One JSON file per state holding **notable non-legislative actions** by
districts, cities, counties and regional bodies: a moratorium, a board policy,
a tool adoption, a procurement decision. This is the layer that shows how AI
is *actually* being treated on the ground, and the direction of each action is
the project's sentiment proxy.

Load (idempotent — the file replaces the state's rows every time):

    python -m app.seed

## Inclusion rule — read this before adding a row

The point of this layer is signal, not coverage. There are ~13,000 districts;
this file set should stay at **tens of rows nationally**. Add an action only if
at least one of these holds:

1. The body is one of the **five largest districts in its state** by
   enrollment, or a **city/county/regional** body acting for many districts.
2. The action got **national trade-press coverage** (K-12 Dive, EdWeek,
   Chalkbeat, EdSource, The 74, District Administration).
3. It is the **first of its kind in that state** (first moratorium, first
   district-wide adoption, first board policy).

Model *events*, never districts: a district with no notable action has no row.
When an action is superseded, set `lifecycle: rescinded` on the old row and add
the new one — don't rewrite history.

## File shape

```json
{
  "state_code": "NY",
  "actions": [
    {
      "jurisdiction": "New York City Public Schools",
      "jurisdiction_type": "district",
      "action_type": "MORATORIUM",
      "direction": -2,
      "applies_to": "students",
      "grade_band": "PK-8",
      "authority": "mayor + chancellor directive",
      "lifecycle": "adopted",
      "effective_from": "2026-09-02",
      "effective_until": "2027-06-30",
      "enrollment": 900000,
      "summary": "One sentence a reader can act on.",
      "notes": "Anything that qualifies the summary.",
      "sources": ["https://..."]
    }
  ]
}
```

| Field | Values | Notes |
|---|---|---|
| `jurisdiction_type` | `district` `city` `county` `region` `consortium` | |
| `action_type` | `MORATORIUM` `RESTRICT` `PERMIT` `ADOPT` `GUIDANCE` `PROCUREMENT` | what kind of move it was |
| `direction` | `-2` … `+2` | **the sentiment proxy.** -2 prohibit, -1 restrict, 0 neutral guidance, +1 permit/encourage, +2 mandate or district-wide adoption |
| `applies_to` | `students` `staff` `both` | default `students` |
| `grade_band` | free text, e.g. `PK-8`, `K-12`, `9-12` | |
| `authority` | free text | *who* decided matters: a board vote outlives a superintendent memo |
| `lifecycle` | `proposed` `adopted` `rescinded` | what a human knows; default `adopted` |
| `effective_from` / `effective_until` | ISO date | leave `effective_until` out for open-ended. **Status (active/expired) is derived from these at read time — never edit a status by hand.** |
| `enrollment` | integer, approximate | weights the state rollup on a log scale; omit if unknown |
| `summary` | required | one or two sentences |
| `notes` | optional | caveats, what's unverified |
| `sources` | list of URLs | at least one, please |

## How it rolls up

`app/derive.py::local_signal()` computes per state, on every read:
`count`, `active`, `leaning` (`restrictive` / `permissive` / `mixed` / none),
`score` (enrollment- and recency-weighted mean direction of *active* actions),
`latest`, and a `headline` action. The map draws a small square on the state
colored by leaning; the state modal lists every action, active first.

A state with no rows reads as "no notable local actions", not "neutral".
