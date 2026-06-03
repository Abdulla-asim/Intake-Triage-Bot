# Intake Triage Bot Write-up

## Why this problem?
Helpdesk and intake teams spend too much time on low-value triage work: reading unstructured requests, deciding urgency, chasing missing contact details, and routing tickets to the right queue. That delay hurts both customers and support teams, especially in clinics and service centers where timing and handoff accuracy matter.

I chose this problem because it is a real operational pain point in support workflows. The notebook and app move beyond a toy example by building a decision flow that gathers missing intake data, chooses a queue, and escalates when a case is out of scope or urgent.

## Who is the user?
The primary user is a frontline intake coordinator, helpdesk agent, or clinic receptionist. They use the bot when a new request arrives via email, chat, or phone note and need a quick, reliable way to capture essential information and route the request correctly.

## Architecture
- `intake_triage_agent.py` defines the triage workflow using `langgraph.StateGraph`.
- The workflow has nodes for parsing incoming requests, generating follow-up questions for missing fields, routing the request to the appropriate queue, creating a ticket summary, and escalating when needed.
- `app.py` exposes a local web interface so the bot is accessible via `http://localhost:8000`.

### Autonomous decisions
- classify request type into categories like Technical, Billing, Scheduling, Medical, Facility, or Other.
- assess urgency as critical/high/medium/low.
- detect missing required intake fields and generate a precise follow-up question.
- route completed requests to the appropriate support queue.
- escalate requests that are outside scope or require immediate human attention.

### Escalation and failure handling
- If the intake is out of scope, the agent marks it for human review instead of forcing a category.
- If required fields are missing, it asks a follow-up question instead of making assumptions.
- If the workflow fails, the agent returns an escalation note that sends the request to a human intake team.

## What did I learn?
- A real intake bot needs more than classification: it must handle missing data, ask for clarification, and avoid giving false confidence.
- A graph-based workflow is a good fit for branching intake logic because it separates parsing, follow-up, routing, and escalation.
- Local deployment with FastAPI makes the bot immediately accessible for testing and handoff, while still letting the user deploy it themselves.
