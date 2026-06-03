from __future__ import annotations

import os
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

load_dotenv()


def create_model(api_key: str | None = None) -> ChatGoogleGenerativeAI:
    if api_key:
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", api_key=api_key)
    env_api_key = os.getenv("GOOGLE_API_KEY")
    if not env_api_key:
        raise EnvironmentError("GOOGLE_API_KEY must be set in the environment or .env file.")
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", api_key=env_api_key)


class IntakeSchema(BaseModel):
    issue_summary: str = Field(description="Short summary of the incoming request")
    issue_type: Literal["Technical", "Billing", "Scheduling", "Medical", "Facility", "Other"] = Field(description="Best-fit category for the request")
    urgency: Literal["critical", "high", "medium", "low"] = Field(description="How urgent the request appears")
    customer_name: str | None = Field(default=None, description="Name of the customer or patient")
    contact: str | None = Field(default=None, description="Best contact method or details")
    requested_action: str = Field(description="What the requester wants to happen")
    required_info_missing: list[str] = Field(default_factory=list, description="Missing required information fields")
    scope: Literal["in_scope", "out_of_scope"] = Field(description="Whether the request is handled by this service team")
    out_of_scope_reason: str | None = Field(default=None, description="Why the request is outside intake scope")


class IntakeState(TypedDict, total=False):
    raw_request: str
    follow_up_answers: list[str] | None
    issue_summary: str
    issue_type: Literal["Technical", "Billing", "Scheduling", "Medical", "Facility", "Other"]
    urgency: Literal["critical", "high", "medium", "low"]
    customer_name: str | None
    contact: str | None
    requested_action: str
    required_info_missing: list[str]
    scope: Literal["in_scope", "out_of_scope"]
    out_of_scope_reason: str | None
    follow_up_question: str
    route: str
    route_notes: str
    ticket_summary: str
    ticket: dict
    escalate: bool
    escalation_reason: str | None


class IntakeTriageAgent:
    def __init__(self) -> None:
        self.model = create_model()
        self.structured_intake_model = self.model.with_structured_output(IntakeSchema)
        self.workflow = self._build_workflow()

    def _build_model(self, api_key: str | None = None):
        if api_key:
            model = create_model(api_key)
            return model, model.with_structured_output(IntakeSchema)
        return self.model, self.structured_intake_model

    def _build_workflow(self) -> StateGraph[IntakeState]:
        graph = StateGraph(IntakeState)
        graph.add_node("parse_intake", self.parse_intake)
        graph.add_node("generate_followup", self.generate_followup)
        graph.add_node("route_request", self.route_request)
        graph.add_node("finalize_ticket", self.finalize_ticket)
        graph.add_node("escalate_human", self.escalate_human)

        graph.add_edge(START, "parse_intake")
        graph.add_conditional_edges(
            "parse_intake",
            self.check_parse_result,
            path_map=["generate_followup", "route_request", "escalate_human"],
        )
        graph.add_edge("generate_followup", END)
        graph.add_edge("route_request", "finalize_ticket")
        graph.add_edge("finalize_ticket", END)
        graph.add_edge("escalate_human", END)

        return graph.compile()

    def parse_intake(self, state: IntakeState) -> dict:
        raw_text = state["raw_request"].strip()
        follow_up_answers = state.get("follow_up_answers") or []
        model = state.get("_model", self.model)
        structured_intake_model = state.get("_structured_model", self.structured_intake_model)
        for idx, answer in enumerate(follow_up_answers, start=1):
            raw_text += f"\n\nFollow-up answer {idx}:\n{answer}"

        prompt = f"""
You are a service intake triage assistant for a helpdesk / clinic / service center.
Read the incoming request below and extract the key fields. Return valid values only.

Input request:
{raw_text}

Return JSON with exactly these fields:
- issue_summary: one-sentence summary of the problem or request.
- issue_type: one of Technical, Billing, Scheduling, Medical, Facility, Other.
- urgency: one of critical, high, medium, low.
- customer_name: the name of the requester if available, otherwise leave blank.
- contact: best contact channel or contact details if available, otherwise leave blank.
- requested_action: what the requester wants to happen.
- required_info_missing: list of required fields still missing for a complete intake. Use exact field names: customer_name, contact, issue_summary, issue_type, urgency, requested_action.
- scope: in_scope if this request belongs to a normal service intake queue, out_of_scope if it is outside the service center's intake capability.
- out_of_scope_reason: if scope is out_of_scope, say why in one short sentence; otherwise leave blank.
"""

        result = structured_intake_model.invoke(prompt)
        parsed = result.model_dump()
        parsed["required_info_missing"] = parsed.get("required_info_missing") or []

        # Enforce required intake fields in case the model omits them.
        required_fields = {
            "customer_name": parsed.get("customer_name"),
            "contact": parsed.get("contact"),
            "issue_summary": parsed.get("issue_summary"),
            "issue_type": parsed.get("issue_type"),
            "urgency": parsed.get("urgency"),
            "requested_action": parsed.get("requested_action"),
        }
        for field, value in required_fields.items():
            text = "" if value is None else str(value).strip()
            if not text or text.lower() in {"unknown", "n/a", "not provided", "none"}:
                if field not in parsed["required_info_missing"]:
                    parsed["required_info_missing"].append(field)

        parsed["required_info_missing"] = list(dict.fromkeys(parsed["required_info_missing"]))
        parsed["follow_up_answers"] = follow_up_answers
        parsed["follow_up_question"] = ""
        parsed["route"] = ""
        parsed["route_notes"] = ""
        parsed["ticket_summary"] = ""
        parsed["ticket"] = {}
        parsed["escalate"] = False
        parsed["escalation_reason"] = None
        return parsed

    def check_parse_result(
        self,
        state: IntakeState,
    ) -> Literal["escalate_human", "generate_followup", "route_request"]:
        if state["scope"] == "out_of_scope":
            return "escalate_human"
        if state["required_info_missing"]:
            return "generate_followup"
        return "route_request"

    def generate_followup(self, state: IntakeState) -> dict:
        missing = state["required_info_missing"]
        fields = ", ".join(missing)
        prompt = f"""
A support intake request is missing required information: {fields}.
Ask one polite, precise follow-up question that will help the requester provide the missing information.
Return only the question text.
"""
        model = state.get("_model", self.model)
        question = model.invoke(prompt).content.strip()
        if not question.endswith("?"):
            question += "?"
        return {
            "follow_up_question": question,
            "escalate": False,
            "escalation_reason": None,
        }

    def route_request(self, state: IntakeState) -> dict:
        route_map = {
            "Technical": "Technical Support",
            "Billing": "Billing Team",
            "Scheduling": "Scheduling / Operations",
            "Medical": "Clinical Triage",
            "Facility": "Facilities / Maintenance",
            "Other": "General Intake / Human Review",
        }
        route = route_map.get(state["issue_type"], "General Intake / Human Review")
        route_notes = []
        escalate = False
        escalation_reason = None

        if state["issue_type"] == "Other":
            route_notes.append("Request did not match a defined intake category; route to human review.")
            escalate = True
            escalation_reason = "Needs human review for classification."

        if state["urgency"] in ["critical", "high"] and state["issue_type"] in ["Medical", "Technical"]:
            route_notes.append("Urgent case; recommend human triage on the destination team.")
            if state["urgency"] == "critical":
                escalate = True
                escalation_reason = "Critical urgency; route for immediate attention."

        if state["scope"] == "out_of_scope":
            route_notes.append("Request is outside normal service intake scope.")
            escalate = True
            escalation_reason = state.get("out_of_scope_reason") or "Out of scope."

        return {
            "route": route,
            "route_notes": " ".join(route_notes).strip(),
            "escalate": escalate,
            "escalation_reason": escalation_reason,
        }

    def finalize_ticket(self, state: IntakeState) -> dict:
        note_lines = []
        if state.get("required_info_missing"):
            note_lines.append(f"Missing fields: {', '.join(state['required_info_missing'])}.")
        if state.get("route_notes"):
            note_lines.append(state["route_notes"])
        if state.get("escalation_reason"):
            note_lines.append(f"Escalation note: {state['escalation_reason']}")

        details = {
            "Issue summary": state["issue_summary"],
            "Issue type": state["issue_type"],
            "Urgency": state["urgency"],
            "Customer name": state.get("customer_name") or "Unknown",
            "Contact": state.get("contact") or "Unknown",
            "Requested action": state["requested_action"],
            "Route": state["route"],
        }
        details_str = "\n".join(f"{k}: {v}" for k, v in details.items())
        prompt = f"""
Create a concise ticket summary for the target support team using the following details:
{details_str}

Also include any intake notes that will help the agent pick up the request quickly.
Return only the summary text.
"""
        model = state.get("_model", self.model)
        ticket_summary = model.invoke(prompt).content.strip()
        if not ticket_summary:
            ticket_summary = f"Intake ticket for {state['route']} with urgency {state['urgency']}."

        return {
            "ticket_summary": ticket_summary,
            "ticket": {
                "summary": ticket_summary,
                "route": state["route"],
                "urgency": state["urgency"],
                "issue_type": state["issue_type"],
                "customer_name": state.get("customer_name"),
                "contact": state.get("contact"),
                "requested_action": state["requested_action"],
                "notes": note_lines,
            },
            "escalate": state.get("escalate", False),
            "escalation_reason": state.get("escalation_reason"),
        }

    def escalate_human(self, state: IntakeState) -> dict:
        reason = state.get("out_of_scope_reason") or "Needs human intake review."
        return {
            "escalate": True,
            "escalation_reason": reason,
            "ticket_summary": "",
            "ticket": {},
        }

    def process(
        self,
        raw_request: str,
        follow_up_answers: list[str] | None = None,
        api_key: str | None = None,
    ) -> dict:
        try:
            model, structured_model = self._build_model(api_key)
            state = {
                "raw_request": raw_request,
                "follow_up_answers": follow_up_answers or [],
                "_model": model,
                "_structured_model": structured_model,
            }
            return self.workflow.invoke(state)
        except Exception as exc:
            return {
                "error": "Failed to run intake triage workflow.",
                "details": str(exc),
                "escalate": True,
                "escalation_reason": "Fallback to human intake due to workflow error.",
            }

    def run_interactive(self) -> None:
        print("Intake Triage Bot interactive mode")
        raw_request = input("Paste the incoming request text:\n")
        follow_up_answers: list[str] = []
        while True:
            result = self.process(raw_request, follow_up_answers=follow_up_answers)
            if result.get("follow_up_question"):
                print("\nFollow-up needed:")
                print(result["follow_up_question"])
                follow_up_answers.append(input("Answer: "))
                continue
            print("\nFinal result:")
            print(result)
            break


if __name__ == "__main__":
    IntakeTriageAgent().run_interactive()
