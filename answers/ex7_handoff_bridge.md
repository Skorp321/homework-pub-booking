# Ex7 — Handoff bridge

## Your answer

In sess_5ce9487419e7 (`make ex7-real`, no Rasa server running) the
HandoffBridge.run loop orchestrated three rounds
before hitting max_rounds. Each round: loop half runs, if
next_action=handoff_to_structured the bridge calls
build_forward_handoff and write_handoff, invokes
structured, and then either marks complete (structured confirmed)
or builds a reverse task and loops back (structured escalated).

The reverse-task path is the interesting one. On escalation
(bridge.py — `if struct_result.next_action == "escalate"`) the
bridge calls build_reverse_task (bridge.py:195), which produces a
dict with prior_result + rejection_reason + retry=True. The loop
half sees this on the next executor invocation and produces a
different subgoal. In my trace this is visible at trace.jsonl event
9: planner.called with `task_preview` "The structured half rejected
the previous proposal. Reason: rasa unreachable…" — that's the
reverse task verbatim. Round 2's subgoal sg_1 (ticket tk_7a435114)
was then "retry with larger venue after rejection".

Every half transition emits a session.state_changed trace event
(bridge.py) via
session.append_trace_event(). The integrity check
(starter/handoff_bridge/integrity.py verifies the trace has
at least one bridge.round_start, at least one
session.state_changed, and at least one executor.tool_called —
catching the case where the bridge reports success without doing
real work.

The stale-handoff cleanup moves old
ipc/handoff_to_structured.json files into logs/handoffs/
(session.handoffs_audit_dir) as `round_<N>_forward.json` instead of
deleting them, preserving the audit trail for post-mortem.

## Citations

- sessions/sess_5ce9487419e7/logs/trace.jsonl (3-round trajectory
  with rasa unreachable rejection at events 7 and 14)
- sessions/sess_5ce9487419e7/logs/tickets/tk_7a435114/raw_output.json
  (round 2 planner output after reverse handoff)
- starter/handoff_bridge/bridge.py: — HandoffBridge.run
- starter/handoff_bridge/integrity.py — verify_dataflow
