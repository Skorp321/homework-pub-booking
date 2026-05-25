"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import (
    ToolError,
    ToolRegistry,
    ToolResult,
    _RegisteredTool,
)

from starter.edinburgh_research.integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


def _load_fixture(filename: str):
    path = _SAMPLE_DATA / filename
    if not path.exists():
        raise ToolError(
            "SA_TOOL_DEPENDENCY_MISSING",
            f"required fixture missing: {path}",
            context={"path": str(path)},
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    arguments = {
        "near": near,
        "party_size": party_size,
        "budget_max_gbp": budget_max_gbp,
    }

    venues = _load_fixture("venues.json")
    open_venues = [v for v in venues if v.get("open_now", False)]
    needle = (near or "").lower().strip()
    party = max(1, int(party_size))
    budget = int(budget_max_gbp)

    def matches_area(v: dict) -> bool:
        return (not needle) or needle in v.get("area", "").lower()

    def matches_seats(v: dict) -> bool:
        return int(v.get("seats_available_evening", 0)) >= party

    def matches_budget(v: dict) -> bool:
        floor = int(v.get("hire_fee_gbp", 0)) + int(v.get("min_spend_gbp", 0))
        return floor <= budget

    strict = [v for v in open_venues if matches_area(v) and matches_seats(v) and matches_budget(v)]
    if strict:
        results, match_mode = strict, "strict"
    else:
        loose = [v for v in open_venues if matches_seats(v) and matches_budget(v)]
        if loose:
            results, match_mode = loose, "area_relaxed"
        else:
            budget_only = [v for v in open_venues if matches_budget(v)]
            if budget_only:
                results, match_mode = budget_only, "seats_relaxed"
            else:
                results, match_mode = open_venues, "budget_relaxed"

    prior_searches = [r for r in _TOOL_CALL_LOG if r.tool_name == "venue_search"]
    if len(prior_searches) >= 2:
        merged: list[dict] = []
        seen_ids: set[str] = set()
        for r in prior_searches:
            for v in r.output.get("results", []) or []:
                vid = v.get("id")
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    merged.append(v)
        for v in results:
            vid = v.get("id")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                merged.append(v)
        if not merged:
            merged = open_venues
        chosen_id = merged[0].get("id") if merged else "haymarket_tap"
        summary = (
            f"venue_search: STOP searching — you have {len(merged)} candidate(s). "
            f"Pick one (e.g. {chosen_id}) and proceed to get_weather, "
            f"calculate_cost, then generate_flyer NEXT."
        )
        output = {
            "near": near,
            "party_size": party_size,
            "results": merged,
            "count": len(merged),
            "instruction": "STOP searching. Pick a venue and continue with get_weather, calculate_cost, generate_flyer.",
            "search_attempts": len(prior_searches) + 1,
        }
        record_tool_call("venue_search", arguments, output)
        return ToolResult(success=True, output=output, summary=summary)

    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
        "match_mode": match_mode,
    }
    summary = f"venue_search({near}, party={party_size}): {len(results)} result(s)"
    if match_mode != "strict":
        summary += f" [relaxed: {match_mode}]"
    record_tool_call("venue_search", arguments, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    arguments = {"city": city, "date": date}
    data = _load_fixture("weather.json")
    city_key = (city or "").strip().lower()
    city_record = data.get(city_key) if isinstance(data, dict) else None
    if not city_record:
        err = ToolError(
            "SA_TOOL_INVALID_INPUT",
            f"city {city!r} not in weather fixture",
            context={
                "city": city,
                "available": list(data.keys()) if isinstance(data, dict) else [],
            },
        )
        output = {"city": city, "date": date, "error": err.message}
        record_tool_call("get_weather", arguments, output)
        return ToolResult(
            success=False,
            output=output,
            summary=f"get_weather({city}, {date}): unknown city",
            error=err,
        )

    day = city_record.get(date)
    if not day:
        err = ToolError(
            "SA_TOOL_INVALID_INPUT",
            f"date {date!r} not in weather fixture for {city!r}",
            context={"city": city, "date": date, "available_dates": list(city_record.keys())},
        )
        output = {"city": city, "date": date, "error": err.message}
        record_tool_call("get_weather", arguments, output)
        return ToolResult(
            success=False,
            output=output,
            summary=f"get_weather({city}, {date}): unknown date",
            error=err,
        )

    output = {
        "city": city,
        "date": date,
        "condition": day["condition"],
        "temperature_c": day["temperature_c"],
        "precip_mm": day.get("precip_mm"),
        "wind_kph": day.get("wind_kph"),
    }
    summary = f"get_weather({city}, {date}): {day['condition']}, {day['temperature_c']}C"
    record_tool_call("get_weather", arguments, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    arguments = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }
    catering = _load_fixture("catering.json")
    venues = _load_fixture("venues.json")

    venue = next((v for v in venues if v.get("id") == venue_id), None)
    if venue is None:
        err = ToolError(
            "SA_TOOL_INVALID_INPUT",
            f"venue_id {venue_id!r} not found in venues.json",
            context={"venue_id": venue_id},
        )
        output = {"venue_id": venue_id, "error": err.message}
        record_tool_call("calculate_cost", arguments, output)
        return ToolResult(
            success=False,
            output=output,
            summary=f"calculate_cost({venue_id}): unknown venue",
            error=err,
        )

    base_rates = catering.get("base_rates_gbp_per_head", {})
    if catering_tier not in base_rates:
        err = ToolError(
            "SA_TOOL_INVALID_INPUT",
            f"unknown catering_tier {catering_tier!r}",
            context={"catering_tier": catering_tier, "available": list(base_rates.keys())},
        )
        output = {"venue_id": venue_id, "error": err.message}
        record_tool_call("calculate_cost", arguments, output)
        return ToolResult(
            success=False,
            output=output,
            summary=f"calculate_cost({venue_id}): unknown catering tier",
            error=err,
        )

    base_per_head = float(base_rates[catering_tier])
    venue_mult = float(catering.get("venue_modifiers", {}).get(venue_id, 1.0))
    hours = max(1, int(duration_hours))

    subtotal = base_per_head * venue_mult * int(party_size) * hours
    service = subtotal * float(catering.get("service_charge_percent", 0)) / 100.0
    venue_floor = int(venue.get("hire_fee_gbp", 0)) + int(venue.get("min_spend_gbp", 0))
    total = subtotal + service + venue_floor

    if total < 300:
        deposit = 0.0
    elif total <= 1000:
        deposit = total * 0.20
    else:
        deposit = total * 0.30

    output = {
        "venue_id": venue_id,
        "party_size": int(party_size),
        "duration_hours": hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": int(round(subtotal)),
        "service_gbp": int(round(service)),
        "total_gbp": int(round(total)),
        "deposit_required_gbp": int(round(deposit)),
    }
    summary = (
        f"calculate_cost({venue_id}, {party_size}): "
        f"total £{output['total_gbp']}, deposit £{output['deposit_required_gbp']}"
    )
    record_tool_call("calculate_cost", arguments, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    details = dict(event_details or {})

    def esc(value: object) -> str:
        return _html.escape(str(value), quote=True)

    def pick(*keys, default=""):
        for k in keys:
            if k in details and details[k] not in (None, ""):
                return details[k]
        return default

    venue_name = pick("venue_name", "name", "venue", default="Edinburgh Venue")
    venue_address = pick("venue_address", "address")
    date = pick("date", "event_date")
    time = pick("time", "event_time", "start_time")
    party_size = pick("party_size", "party", "size")
    condition = pick("condition", "weather_condition", "weather")
    temperature_c = pick("temperature_c", "temperature", "temp_c", "temp")
    total_gbp = pick("total_gbp", "total_cost_gbp", "total_cost", "total")
    deposit_required_gbp = pick(
        "deposit_required_gbp", "deposit_gbp", "deposit_required", "deposit"
    )

    html_doc = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>Booking at {esc(venue_name)}</title>\n"
        "  <style>\n"
        "    body { font-family: -apple-system, system-ui, sans-serif; max-width: 640px;"
        " margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }\n"
        "    article { border: 1px solid #ddd; border-radius: 8px; padding: 1.5rem;"
        " background: #fafafa; }\n"
        "    h1 { margin-top: 0; color: #2a4d69; }\n"
        "    dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.5rem 1rem; }\n"
        "    dt { font-weight: 600; color: #555; }\n"
        "    dd { margin: 0; }\n"
        "    .cost { font-size: 1.2rem; font-weight: 700; color: #2a4d69; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <article>\n"
        f'    <h1 data-testid="title">Booking at <span data-testid="venue-name">{esc(venue_name)}</span></h1>\n'
        "    <section>\n"
        "      <h2>Event details</h2>\n"
        "      <dl>\n"
        f'        <dt>Address</dt><dd data-testid="venue-address">{esc(venue_address)}</dd>\n'
        f'        <dt>Date</dt><dd data-testid="date">{esc(date)}</dd>\n'
        f'        <dt>Time</dt><dd data-testid="time">{esc(time)}</dd>\n'
        f'        <dt>Party size</dt><dd data-testid="party-size">{esc(party_size)}</dd>\n'
        "      </dl>\n"
        "    </section>\n"
        "    <section>\n"
        "      <h2>Weather forecast</h2>\n"
        "      <dl>\n"
        f'        <dt>Condition</dt><dd data-testid="condition">{esc(condition)}</dd>\n'
        f'        <dt>Temperature</dt><dd data-testid="temperature">{esc(temperature_c)}&deg;C</dd>\n'
        "      </dl>\n"
        "    </section>\n"
        "    <section>\n"
        "      <h2>Cost</h2>\n"
        "      <dl>\n"
        f'        <dt>Total</dt><dd class="cost" data-testid="total">&pound;{esc(total_gbp)}</dd>\n'
        f'        <dt>Deposit</dt><dd data-testid="deposit">&pound;{esc(deposit_required_gbp)}</dd>\n'
        "      </dl>\n"
        "    </section>\n"
        "  </article>\n"
        "</body>\n"
        "</html>\n"
    )

    workspace = session.workspace_dir
    workspace.mkdir(parents=True, exist_ok=True)
    flyer_path = workspace / "flyer.html"
    bytes_written = flyer_path.write_text(html_doc, encoding="utf-8")

    output = {
        "path": "workspace/flyer.html",
        "bytes_written": bytes_written,
        "venue_name": venue_name,
        "date": date,
        "time": time,
        "party_size": party_size,
        "condition": condition,
        "temperature_c": temperature_c,
        "total_gbp": total_gbp,
        "deposit_required_gbp": deposit_required_gbp,
    }
    summary = f"generate_flyer: wrote {output['path']} ({bytes_written} chars)"
    record_tool_call("generate_flyer", {"event_details": details}, output)
    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
