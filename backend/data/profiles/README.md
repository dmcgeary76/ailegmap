# State profiles

One JSON file per jurisdiction holding the **manually researched** layer: state
education agency guidance, regulatory stance, maturity, context, and sources.
Bills are *not* here — they come from the LegiScan sync and live in the `bills`
table.

Load (idempotent — re-run any time a file changes):

    python -m app.seed

Fields: `state_code`, `research_status` (RESEARCHED / NOT_RESEARCHED),
`guidance_exists`, `guidance_type` (MANDATORY / ADVISORY / PROPOSED / NONE),
`guidance_issued_by`, `guidance_issued_date` (ISO), `guidance_url`,
`guidance_core_principles[]`, `regulatory_stance`
(PROHIBIT / RESTRICT / REGULATE / SUPPORT / MANDATE / ABSENT), `maturity`
(NASCENT / IN_PROGRESS / ACTIVE / MATURE), `key_focus_areas[]`,
`unique_context`, `notes`, `sources[]`.

A jurisdiction with no file here shows as "not yet assessed" in the app.
District/city/county activity does **not** go in `unique_context` any more — it
has its own structured layer in `../local_actions/` (see that README).
Worth a second look: the original pilot load classified California as
PROHIBIT, which is carried over here unchanged, but CA's framework (CDE
guidance plus the SB1288 working-group statute) reads more like REGULATE.
