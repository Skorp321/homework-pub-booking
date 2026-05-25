# Ex5 — Edinburgh research loop scenario

## Your answer

In session sess_41266642824a (`make ex5-real`, openai/gpt-oss-120b
planner+executor) the real planner produced five subgoals, all
assigned to the loop half — sg_1 search venues near Haymarket, sg_2
get the weather for 2026-04-25, sg_3 calculate the cost, sg_4
generate the HTML flyer, sg_5 complete the task. The offline
`make ex5` (FakeLLMClient) script collapses sg_1–sg_3 into one
parallel turn because all three reads are parallel_safe; the real
LLM serialised them.

The trace (logs/trace.jsonl, 15 tool events) shows the LLM deviated
from the task: it widened the search to "Edinburgh" after the
strict-area match returned only Haymarket Tap, tried date
"2024-10-01" (unknown-date error, recorded as success=False), then
settled on 2026-05-01 (sunny, 17°C) and Bennet's Bar with party=20.
The spiral guard inside venue_search fired on the third call
(L10: "STOP searching — you have 4 candidate(s)") which kept the
executor from looping indefinitely.

The final flyer at workspace/flyer.html names Bennet's Bar, party
20, sunny 17°C, total £1941, deposit £582 — all values that
actually came out of the tools at L13–L14. verify_dataflow returned
ok=True even though the LLM ignored the task constraints, because
every concrete fact in the flyer can be traced to a real tool call
in the same session. That is the deliberate design: the integrity
check guards against **fabrication** (a flyer claim that no tool
ever produced), not against **parameter drift** (the LLM choosing
the wrong party size). Drift is a task-success concern, not a
data-integrity one.

## Citations

- sessions/sess_41266642824a/logs/trace.jsonl (15 tool events,
  including spiral guard fire at L10 and final generate_flyer at L15)
- sessions/sess_41266642824a/workspace/flyer.html (Bennet's Bar
  flyer, all fields traceable to L13–L14 tool outputs)
- sessions/sess_41266642824a/logs/tickets/ (planner ticket holds
  the 5-subgoal decomposition; executor tickets hold per-subgoal
  tool-call lists)
