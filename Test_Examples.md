# Intake Triage Bot 

## How it works

- Paste an incoming helpdesk or clinic request into the form.
- The agent extracts category, urgency, contact details, and requested action.
- If required intake details are missing, it asks a single follow-up question.
- If the request is outside scope or needs escalation, it marks the request for human review.
- When intake is complete, it returns a routed ticket summary and a suggested queue.

## Test examples

Use requests like:

- “Patient Maria Lee called because her 9am physical therapy appointment must be moved to tomorrow morning; she’s now running a 101°F fever and wants to keep the same therapist if possible. Contact: maria.lee@healthmail.com, phone 555-123-6789.”

- “We have multiple customers unable to complete checkout on the enterprise billing portal. The error page shows `PAYMENT_GATEWAY_TIMEOUT`, and this started after the last deploy. This looks like a production outage, so please escalate to technical ops.”
* “Front desk reports a patient arrived for a dermatology consult but the room temperature system is down and the clinic is overflowed. They need facilities support plus a quick reschedule option for the patient.”

* “A user says their subscription was billed twice and they need an urgent correction before the next payment cycle. They included account email sam.wong@company.com but no customer ID.”“A long-term client needs a refund for invoice #INV-89412; they say the service was never delivered and they only have the order date 2026-05-21. Ask for the account ID and any purchase reference.”
