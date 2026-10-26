#!/usr/bin/env python3
"""
Example CrewAI Flow — Ticket Triage & Response System

This is a REFERENCE EXAMPLE demonstrating all required challenge patterns:
  ✓ 3+ agents with distinct roles
  ✓ Typed state with 5+ fields (Pydantic BaseModel)
  ✓ State mutations across steps
  ✓ Conditional routing based on priority
  ✓ Custom tool (sentiment analysis)
  ✓ Error handling
  ✓ Structured output

Do NOT extend this file — build your own Flow from scratch.
"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, listen, router, start
from crewai.tools import tool

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("MODEL_NAME", "gemini/gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Custom Tool — demonstrates the @tool pattern
# ---------------------------------------------------------------------------
@tool("Sentiment Analyzer")
def analyze_sentiment(text: str) -> str:
    """Analyze the sentiment of the given text. Returns positive, negative, or neutral with a confidence score."""
    # In a real scenario this could call an NLP API.
    # Here we use simple keyword matching as a placeholder.
    positive_words = {"great", "fantastic", "love", "excellent", "good", "nice", "thank", "happy", "awesome", "wonderful"}
    negative_words = {"bad", "terrible", "hate", "awful", "worst", "angry", "frustrated", "broken", "crash", "issue", "problem", "urgent"}

    words = set(text.lower().split())
    pos_count = len(words & positive_words)
    neg_count = len(words & negative_words)
    total = pos_count + neg_count or 1

    if pos_count > neg_count:
        sentiment, confidence = "positive", round(pos_count / total, 2)
    elif neg_count > pos_count:
        sentiment, confidence = "negative", round(neg_count / total, 2)
    else:
        sentiment, confidence = "neutral", 0.5

    return json.dumps({"sentiment": sentiment, "confidence": confidence})


# ---------------------------------------------------------------------------
# Structured Output — Pydantic model for the final result
# ---------------------------------------------------------------------------
class TicketResolution(BaseModel):
    ticket_id: str = Field(description="Original ticket ID")
    priority: str = Field(description="Assessed priority: high, medium, or low")
    sentiment: str = Field(description="Customer sentiment")
    category: str = Field(description="Ticket category")
    suggested_response: str = Field(description="Draft response to the customer")
    requires_escalation: bool = Field(description="Whether this needs human escalation")


# ---------------------------------------------------------------------------
# Flow State — typed state with 5+ fields
# ---------------------------------------------------------------------------
class TicketTriageState(BaseModel):
    # Input
    ticket_raw: str = ""
    # Populated during flow
    ticket_id: str = ""
    priority: str = ""
    sentiment: str = ""
    category: str = ""
    classification_summary: str = ""
    research_notes: str = ""
    draft_response: str = ""
    requires_escalation: bool = False
    # Final output
    resolution: Optional[TicketResolution] = None


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
classifier_agent = Agent(
    role="Ticket Classifier",
    goal="Accurately classify support tickets by priority, category, and customer sentiment.",
    backstory=(
        "You are an experienced support operations analyst. You triage incoming "
        "tickets quickly and accurately so they reach the right team."
    ),
    tools=[analyze_sentiment],
    llm=MODEL_NAME,
    verbose=False,
)

researcher_agent = Agent(
    role="Knowledge Base Researcher",
    goal="Find relevant solutions and context for customer issues.",
    backstory=(
        "You have deep knowledge of the company's products and policies. You dig "
        "into the knowledge base to find the best answer for each ticket."
    ),
    llm=MODEL_NAME,
    verbose=False,
)

writer_agent = Agent(
    role="Response Writer",
    goal="Write empathetic, helpful customer responses.",
    backstory=(
        "You are a skilled customer communications specialist. You craft clear, "
        "warm responses that solve the customer's problem and leave them satisfied."
    ),
    llm=MODEL_NAME,
    verbose=False,
)


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------
class TicketTriageFlow(Flow[TicketTriageState]):

    @start()
    def classify_ticket(self):
        """Step 1 — Classify the incoming ticket."""
        print("[Flow] Step 1: Classifying ticket...")
        try:
            task = Task(
                description=(
                    f"Analyze this support ticket and provide:\n"
                    f"1. Priority (high / medium / low)\n"
                    f"2. Category (billing, technical_issue, account_access, sales_inquiry, feedback)\n"
                    f"3. Use the Sentiment Analyzer tool on the customer message\n\n"
                    f"Ticket:\n{self.state.ticket_raw}"
                ),
                expected_output=(
                    "A brief summary with exactly these fields on separate lines:\n"
                    "Priority: <high|medium|low>\n"
                    "Category: <category>\n"
                    "Sentiment: <positive|negative|neutral>"
                ),
                agent=classifier_agent,
            )
            result = Crew(agents=[classifier_agent], tasks=[task]).kickoff()
            output = str(result)

            # Parse simple fields from output
            for line in output.splitlines():
                lower = line.lower().strip()
                if lower.startswith("priority:"):
                    self.state.priority = lower.split(":", 1)[1].strip()
                elif lower.startswith("category:"):
                    self.state.category = lower.split(":", 1)[1].strip()
                elif lower.startswith("sentiment:"):
                    self.state.sentiment = lower.split(":", 1)[1].strip()

            self.state.classification_summary = output
            print(f"[Flow]   → Priority={self.state.priority}, Category={self.state.category}, Sentiment={self.state.sentiment}")

        except Exception as e:
            print(f"[Flow]   ✗ Classification failed: {e}")
            self.state.priority = "high"
            self.state.category = "unknown"
            self.state.sentiment = "unknown"
            self.state.requires_escalation = True

    @router(classify_ticket)
    def route_by_priority(self):
        """Conditional router — decides next step based on priority."""
        if self.state.priority == "high":
            return "urgent"
        elif self.state.priority == "medium":
            return "standard"
        else:
            return "low"

    @listen("urgent")
    def handle_urgent(self):
        """Handle high-priority tickets with full research."""
        print("[Flow] Step 2a: Urgent path — deep research...")
        self.state.requires_escalation = True
        self._research_ticket(depth="thorough")

    @listen("standard")
    def handle_standard(self):
        """Handle medium-priority tickets with standard research."""
        print("[Flow] Step 2b: Standard path — normal research...")
        self._research_ticket(depth="standard")

    @listen("low")
    def handle_low(self):
        """Handle low-priority tickets with quick research."""
        print("[Flow] Step 2c: Low-priority path — quick research...")
        self._research_ticket(depth="brief")

    def _research_ticket(self, depth: str):
        """Shared research step used by all priority paths."""
        try:
            task = Task(
                description=(
                    f"Research a solution for this customer ticket.\n"
                    f"Classification: {self.state.classification_summary}\n"
                    f"Research depth: {depth}\n"
                    f"Original ticket:\n{self.state.ticket_raw}\n\n"
                    f"Provide key findings and a recommended approach."
                ),
                expected_output="Research notes with recommended solution approach.",
                agent=researcher_agent,
            )
            result = Crew(agents=[researcher_agent], tasks=[task]).kickoff()
            self.state.research_notes = str(result)
        except Exception as e:
            print(f"[Flow]   ✗ Research failed: {e}")
            self.state.research_notes = "Research unavailable — escalate to senior agent."
            self.state.requires_escalation = True

    @listen(handle_urgent, handle_standard, handle_low)
    def write_response(self):
        """Step 3 — Draft the customer response."""
        print("[Flow] Step 3: Writing response...")
        try:
            task = Task(
                description=(
                    f"Write a customer response for this ticket.\n\n"
                    f"Priority: {self.state.priority}\n"
                    f"Category: {self.state.category}\n"
                    f"Sentiment: {self.state.sentiment}\n"
                    f"Research Notes: {self.state.research_notes}\n"
                    f"Original ticket:\n{self.state.ticket_raw}\n\n"
                    f"Write a professional, empathetic response that addresses the customer's issue."
                ),
                expected_output="A ready-to-send customer response.",
                agent=writer_agent,
            )
            result = Crew(agents=[writer_agent], tasks=[task]).kickoff()
            self.state.draft_response = str(result)
        except Exception as e:
            print(f"[Flow]   ✗ Response writing failed: {e}")
            self.state.draft_response = "We have received your ticket and a specialist will follow up shortly."
            self.state.requires_escalation = True

    @listen(write_response)
    def finalize(self):
        """Step 4 — Build the structured resolution output."""
        print("[Flow] Step 4: Finalizing resolution...")
        self.state.resolution = TicketResolution(
            ticket_id=self.state.ticket_id,
            priority=self.state.priority,
            sentiment=self.state.sentiment,
            category=self.state.category,
            suggested_response=self.state.draft_response,
            requires_escalation=self.state.requires_escalation,
        )
        print(f"[Flow] ✓ Done — escalation={'yes' if self.state.requires_escalation else 'no'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Load a sample ticket from mock data
    mock_path = Path(__file__).parent / "mock_data" / "tickets.json"
    with open(mock_path) as f:
        tickets = json.load(f)

    ticket = tickets[0]  # Use first ticket as example
    print(f"\n{'='*60}")
    print(f"Processing ticket: {ticket['id']} — {ticket['subject']}")
    print(f"{'='*60}\n")

    # Run the flow
    flow = TicketTriageFlow()
    flow.state.ticket_raw = json.dumps(ticket, indent=2)
    flow.state.ticket_id = ticket["id"]

    flow.kickoff()

    # Print result
    if flow.state.resolution:
        print(f"\n{'='*60}")
        print("RESOLUTION")
        print(f"{'='*60}")
        print(flow.state.resolution.model_dump_json(indent=2))
    else:
        print("\nNo resolution produced — check errors above.")


if __name__ == "__main__":
    main()
