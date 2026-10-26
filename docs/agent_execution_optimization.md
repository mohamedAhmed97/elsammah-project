# Agent Execution Time Optimization in CrewAI

When working with CrewAI and lightweight models (e.g., `gemini-2.5-flash`), agent tasks may unexpectedly take around 1 minute and 30 seconds per node. This behavior is usually driven by underlying framework defaults and formatting retries rather than text processing constraints.

## Root Causes

### 1. The ReAct Loop and Unnecessary Delegation
By default, CrewAI agents operate on a ReAct (Reasoning + Acting) loop. The agent enters a cycle of:
- **Thought**: Figuring out what to do.
- **Action**: Trying to call a tool or delegate a task.
- **Observation**: Evaluating the tool's return or discovering it failed.

Without explicit guardrails (`allow_delegation=False` and bounded `max_iter`), agents often spend 30+ seconds debating internally over whether to delegate work or attempt actions they aren't equipped to handle before finally supplying an answer. 

### 2. Pydantic Validation Retries
When your agent outputs strongly-typed Pydantic classes (e.g., `output_pydantic=DemandForecast`), the underlying output parser expects raw, valid JSON. 
If the LLM returns JSON enclosed in Markdown code blocks (e.g., ` ```json \n {...} \n ``` `) or misses a required parameter, the Pydantic parser fails to deserialize the response. 

Instead of crashing, CrewAI traps the error and sends the error message back to the LLM, asking it to fix the format. This prompt-validation loop can run several times until the LLM produces the correct unformatted JSON string, which consumes significant execution time.

### 3. Context Payload Size (Minor impact)
Passing large blocks of raw historical transcripts and courses to the LLM inherently takes longer to read and process. However, modern models parse this quite quickly. This is typically a fraction of the 1:30m delay, with retry logic historically driving the majority of latency.

---

## Best Practices & Immediate Fixes

To drastically cut down latency across the pipeline:

### 1. Disable Delegation & Limit Iterations
Inject these direct configuration flags to the `Agent(...)` constructors to force direct answering:
- `allow_delegation=False`: Prevents the agent from endlessly pausing to consider delegating the work to imaginary peers.
- `max_iter=1` (or `max_iter=2`): Caps the number of times the internal model can ReAct before outputting a result.

```python
agent = Agent(
    role="...",
    goal="...",
    backstory="...",
    llm="MODEL_NAME",
    allow_delegation=False,
    max_iter=2,          # Force swift decisions without looping
    verbose=False
)
```

### 2. Explicit JSON Formatting Instructions
Modify the `expected_output` string inside your `Task(...)` definitions to explicitly command the LLM not to use markdown code blocks or wrapper text.

**Example addition to `expected_output`:**
```text
"Return strictly valid raw JSON with no Markdown wrappers, no backticks, and no conversational text. Start directly with { and end with }."
```

By preventing Pydantic validation failures in the first place, you eliminate the 30-60 second retry delays common in production flows.
