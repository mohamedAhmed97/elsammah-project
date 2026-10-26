# CrewAI Flow — Quick Reference

> This cheatsheet covers the patterns you need for the BPO Innovation Challenge.
> For full docs: [docs.crewai.com](https://docs.crewai.com)

---

## Flow Basics

A **Flow** orchestrates a sequence of steps. Each step can run agents, transform data, or route to other steps.

```python
from crewai.flow.flow import Flow, start, listen, router

class MyFlow(Flow[MyState]):

    @start()
    def first_step(self):
        # This runs first
        self.state.some_field = "value"

    @listen(first_step)
    def second_step(self):
        # This runs after first_step completes
        print(self.state.some_field)
```

### Running a Flow

```python
flow = MyFlow()
flow.kickoff()
```

---

## State (Typed with Pydantic)

State is shared across all steps. Define it as a Pydantic `BaseModel`:

```python
from pydantic import BaseModel, Field
from typing import Optional

class MyState(BaseModel):
    input_text: str = ""
    category: str = ""
    score: float = 0.0
    results: list[str] = Field(default_factory=list)
    final_output: Optional[str] = None
```

Access and mutate state in any step:

```python
self.state.category = "billing"
self.state.results.append("new finding")
```

---

## Decorators

| Decorator | Purpose | Example |
|-----------|---------|---------|
| `@start()` | Entry point of the flow | `@start()` |
| `@listen(step)` | Run after a specific step | `@listen(classify)` |
| `@listen(step1, step2)` | Run after ANY of the listed steps | `@listen(path_a, path_b)` |
| `@router(step)` | Route to different paths after a step | `@router(classify)` |

### Router Example

```python
@router(classify_step)
def route_by_type(self):
    if self.state.priority == "high":
        return "urgent"      # triggers @listen("urgent")
    else:
        return "standard"    # triggers @listen("standard")

@listen("urgent")
def handle_urgent(self):
    ...

@listen("standard")
def handle_standard(self):
    ...
```

### Combining Listeners (or_ / and_)

```python
from crewai.flow.flow import or_, and_

@listen(or_(step_a, step_b))   # runs when EITHER completes
def after_any(self): ...

@listen(and_(step_a, step_b))  # runs when BOTH complete
def after_all(self): ...
```

---

## Agents

```python
from crewai import Agent

agent = Agent(
    role="Data Analyst",
    goal="Analyze customer data to find trends.",
    backstory="You are an expert data analyst with 10 years of BPO experience.",
    tools=[my_custom_tool],          # optional
    llm="gemini/gemini-2.5-flash",   # model name via LiteLLM
    verbose=False,
)
```

### Key Agent Parameters

| Parameter | Description |
|-----------|-------------|
| `role` | Agent's job title / function |
| `goal` | What the agent is trying to achieve |
| `backstory` | Context that shapes the agent's approach |
| `tools` | List of tools the agent can use |
| `llm` | Model name (LiteLLM format) |
| `verbose` | Print detailed reasoning (default: False) |

---

## Tasks

```python
from crewai import Task

task = Task(
    description="Analyze the following ticket and classify it...",
    expected_output="Priority: high/medium/low, Category: ...",
    agent=my_agent,
    output_pydantic=MyOutputModel,  # optional: structured output
)
```

### Running Tasks via Crew

```python
from crewai import Crew

crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2],
)
result = crew.kickoff()
```

---

## Custom Tools

```python
from crewai.tools import tool

@tool("Tool Name")
def my_tool(parameter: str) -> str:
    """Description of what this tool does. This docstring is shown to the agent."""
    # Your logic here
    return "result"
```

Tools are passed to agents via `tools=[my_tool]`. The agent decides when to use them based on the description.

---

## LLM Configuration with LiteLLM

Set these in your `.env` file:

```
LITELLM_API_KEY=your-key
LITELLM_BASE_URL=your-endpoint
MODEL_NAME=gemini/gemini-2.5-flash
```

Use in code:

```python
import os
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("MODEL_NAME", "gemini/gemini-2.5-flash")

agent = Agent(
    role="...",
    goal="...",
    backstory="...",
    llm=MODEL,
)
```

---

## Structured Output with Pydantic

Define an output model:

```python
class AnalysisResult(BaseModel):
    category: str
    confidence: float
    summary: str
```

Use it in a Task:

```python
task = Task(
    description="...",
    expected_output="...",
    agent=my_agent,
    output_pydantic=AnalysisResult,
)

result = crew.kickoff()
# result.pydantic contains a validated AnalysisResult
```

---

## Error Handling

Wrap crew/task execution in try/except:

```python
try:
    result = crew.kickoff()
    self.state.output = str(result)
except Exception as e:
    print(f"Agent task failed: {e}")
    self.state.output = "Fallback value"
    self.state.needs_escalation = True
```

---

## Common Patterns

### Loading Mock Data

```python
import json
from pathlib import Path

data_path = Path(__file__).parent / "mock_data" / "tickets.json"
with open(data_path) as f:
    tickets = json.load(f)
```

### Multi-Agent Pipeline in a Flow Step

```python
@listen(previous_step)
def analyze_and_respond(self):
    analyze_task = Task(description="...", agent=analyst, expected_output="...")
    respond_task = Task(description="...", agent=writer, expected_output="...")

    crew = Crew(
        agents=[analyst, writer],
        tasks=[analyze_task, respond_task],  # runs sequentially
    )
    result = crew.kickoff()
    self.state.response = str(result)
```

---

## Challenge Requirements Checklist

- [ ] 3+ agents with distinct roles
- [ ] Typed state (Pydantic BaseModel) with 5+ fields
- [ ] State mutations across multiple steps
- [ ] At least 1 conditional router
- [ ] At least 1 custom tool (`@tool`)
- [ ] Error handling (try/except around agent tasks)
- [ ] Structured output (Pydantic model)

### Bonus Points

- [ ] MCP server integration
- [ ] Additional custom tools (APIs, databases, web scraping)
- [ ] Streamlit or Gradio UI
- [ ] Real external integrations (email, Slack, database)
