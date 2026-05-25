# Ex6 — Rasa structured half

## Your answer

The RasaStructuredHalf subclass in
starter/rasa_half/structured_half.py overrides run() to POST a
booking intent to Rasa's REST webhook (urllib_request,
structured_half.py:103-113) and interpret the response. Input flow:
loop half produces raw booking data → StructuredHalf calls
normalise_booking_payload (validator.py:54) to produce a Rasa-shaped
message with canonical types → urllib POST to Rasa → parse response
for {action: committed} or {action: rejected} custom slots.

For offline mode (the only mode without a Rasa license) we spawn a
stdlib http.server thread that mimics a Rasa webhook —
spawn_mock_rasa in structured_half.py, built on
ThreadingHTTPServer (structured_half.py). It always confirms,
which is enough for unit tests. Rejection is exercised in Ex7
(sess_5ce9487419e7) where the bridge handles the reverse handoff
when the real Rasa is unreachable.

Three design choices worth noting: (1) we raise ValidationFailed
(validator.py:38) in normalise_booking_payload and catch it in
run() rather than letting it propagate; the StructuredHalf contract
demands a HalfResult. (2) Network errors return success=False with
SA_EXT_SERVICE_UNAVAILABLE (structured_half.py) — the
caller decides whether to retry. (3) The stable sender_id is a
sha1 hash of (venue+date+time) via hashlib (structured_half.py,
468) so the Rasa tracker is consistent across retries within one
session.

## Citations

- starter/rasa_half/validator.py — normalise_booking_payload
- starter/rasa_half/validator.py — ValidationFailed
- starter/rasa_half/structured_half.py — RasaStructuredHalf
- starter/rasa_half/structured_half.py — spawn_mock_rasa
