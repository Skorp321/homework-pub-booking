# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my Ex7 run (session sess_5ce9487419e7, offline FakeLLMClient
trajectory) the planner produced exactly one subgoal per round,
both assigned to the loop half, not to the structured half:

  - Round 1 planner ticket tk_dad285a1: sg_1 "find venue near
    haymarket for 12" — assigned_half: "loop".
  - Round 2 planner ticket tk_7a435114 (after structured rejected
    with "rasa unreachable"): sg_1 "retry with larger venue after
    rejection" — also assigned_half: "loop".

So in this scenario the planner did NOT pre-commit a forward
handoff. The decision to cross the boundary was made by the
executor LLM mid-subgoal, by emitting a handoff_to_structured tool
call (trace.jsonl:5 in round 1, trace.jsonl:12 in round 2). The
HandoffBridge then wrote ipc/handoff_to_structured.json and invoked
the structured half — but the planner's subgoal record itself stays
"loop" forever, even though the run ends up bouncing into
structured.

That's the lesson: there are two distinct handoff loci in
sovereign-agent. The planner CAN pre-commit by setting
`assigned_half: "structured"` on a subgoal — useful when the task
text itself names a deterministic constraint ("under policy rules",
"validate against rules"). The executor LLM can also hand off
opportunistically, after partial work, by calling the built-in
handoff_to_structured tool with a reason and data payload.

Mine fell into the second pattern because my Ex7 task prompt was
"book for party of 12 in Haymarket" — no rule keyword, so the
planner treated the whole thing as a loop-half exploration. Only
after gathering venue candidates does the executor decide "this
needs policy validation" and pull the trigger.

If I wanted the planner to take the decision instead, I'd rewrite
the task to "book under policy: party ≤ 8, deposit ≤ £300", which
biases DefaultPlanner toward emitting a structured-assigned subgoal
directly.

### Citation

- sessions/sess_5ce9487419e7/logs/tickets/tk_dad285a1/raw_output.json
- sessions/sess_5ce9487419e7/logs/trace.jsonl (events 1-7, round 1)

---

## Q2 — Dataflow integrity catch

### Your answer

During `make ex5-real` (session sess_794fe284c5ec, planner +
executor both openai/gpt-oss-120b) verify_dataflow
caught a multi-field fabrication that a human skim would have
missed.

Ground truth recorded in _TOOL_CALL_LOG (trace.jsonl events 4 and 6):
  - get_weather('Edinburgh', '2026-04-25') → condition='cloudy',
    temperature_c=12.
  - calculate_cost('haymarket_tap', party=6, hours=3, bar_snacks)
    → total_gbp=556, deposit_required_gbp=111.

What the LLM wrote into workspace/flyer.html (trace.jsonl event 8,
generate_flyer call):
  - venue_name: "The Royal Botanic Garden Edinburgh, Glasshouses"
    (not in venues.json — Glasshouses isn't a fixture venue)
  - venue_address: "East Gate, Edinburgh EH3 5LR, United Kingdom"
  - date: "2026-07-15" (task and previous get_weather call used
    2026-04-25)
  - party_size: 30 (task said 6)
  - condition: "Sunny, 22°C" (real was cloudy 12°C)
  - deposit: "£500" (real was £111)

verify_dataflow returned ok=False with unverified_facts=['22',
'sunny']. The scalar matcher in fact_appears_in_log lowercases and
strips £/°/C and then scans recursively through every tool call's
arguments+output. '12' and 'cloudy' would have matched (they're
literally in get_weather's output), but '22' and 'sunny' had no
producer anywhere in the session, so they were flagged.

The fabrication is reproducible: an instruction-following LLM with
weak grounding will gladly invent UK pub names and hot-summer
weather even when the task explicitly named the date and the
Haymarket area. The check works because it compares against a
ground-truth log instead of "does this look reasonable"; £500 on a
£500-min-spend pub does not look unreasonable to a human reader.

This is the same shape as the grader's planted-£9999 fabrication
test (README's "fabrication test"), but caught for free on a real
LLM run, on a different LLM, with different fabricated values. The
generality means the check earns its keep on inputs we never
designed for.

### Citation

- sessions/sess_794fe284c5ec/workspace/flyer.html (rendered fields)
- sessions/sess_794fe284c5ec/logs/trace.jsonl (events 3-8, full
  tool sequence)

---

## Q3 — Removing one framework primitive

### Your answer

The one primitive I would refuse to remove is **session directories**
(Decision 1). The single failure mode I want to name is:
**post-mortem forensics become impossible without `cat`-able
evidence at known filesystem paths.**

Concretely, every other primitive in sovereign-agent — tickets,
atomic-rename IPC, the two-halves architecture, the forward-only
state machine — is debuggable today because each one writes its
state into a predictable file inside a session directory. The
bridge writes ipc/handoff_to_structured.json before invoking
structured. The planner writes
logs/tickets/tk_*/raw_output.json with the exact subgoal list. Tool
calls append to logs/trace.jsonl as JSONL. Every concrete question
that came up during this homework — "did the LLM actually call
get_weather?", "what venue did the planner pick on retry?", "why
did the bridge hit max_rounds?" — answered to one `cat` or `jq`
against the session directory, sub-second, no databases.

Without that root, every other primitive still nominally exists but
loses its audit trail. Tickets become opaque function returns.
Reverse handoffs become a void: "structured rejected" with no log
of which arguments it saw. The bridge's
rejection_reason='rasa unreachable' from my sess_5ce9487419e7 trace
is one grep away today; without directories it would live in
process memory only and be lost the moment the bridge exits.
The grader's "cross-references against sessions/ artifacts" rule
also becomes impossible to honor — there is no artifact to
cross-reference.

The framework's own slides compare session directories to git
commits, and the comparison holds: every reproducible debug
primitive in git (diff, blame, log, bisect) is derivable from the
commit DAG, but not the other way around. Take commits away and you
don't have git — you have an opaque tarball generator. Take session
directories away and you don't have sovereign-agent — you have an
LLM loop with no memory the user can read.

### Citation

- sessions/sess_5ce9487419e7/logs/trace.jsonl (bridge state
  transitions; rejection_reason recoverable via grep)
- sessions/sess_794fe284c5ec/logs/trace.jsonl (Ex5 fabrication
  catch; ground-truth tool log enables the check)
