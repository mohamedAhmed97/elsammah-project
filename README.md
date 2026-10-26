# CrewAI BPO Innovation Challenge — Starter Repository

Build a **CrewAI Flow** that solves a real BPO problem using AI agents.

> For full challenge details, scoring criteria, and example scenarios, visit the [Challenge Website](https://konecta-hackathon.web.app).

---

## Quick Setup

### Prerequisites

- **Python 3.10+**
- **uv** (recommended) or pip — [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Git**

### Steps

```bash
# 1. Clone this repository
git clone https://github.com/mikifriki/crewai-bpo-challenge.git
cd crewai-bpo-challenge

# 2. Create virtual environment
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your LiteLLM API key (provided by organizers)

# 5. Verify setup
python verify_setup.py
```

All checks should pass before you start building.

---

## Repository Structure

```
├── README.md                 # You are here
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
├── verify_setup.py           # Setup verification script
├── example_flow.py           # Reference example (DO NOT extend — build your own)
├── mock_data/
│   ├── tickets.json          # Sample customer support tickets
│   ├── agent_metrics.json    # Sample agent performance data
│   └── campaigns.json        # Sample marketing campaign messages
└── docs/
    └── crewai_cheatsheet.md  # Quick reference for CrewAI Flow API
```

---

## What to Build

Create a CrewAI Flow that addresses a BPO challenge. Your flow must include:

| Requirement | Minimum |
|-------------|---------|
| Agents | 3+ with distinct roles |
| Typed State | Pydantic BaseModel, 5+ fields |
| Conditional Routing | 1+ router |
| Custom Tools | 1+ using `@tool` decorator |
| Error Handling | try/except around agent tasks |
| Structured Output | Pydantic model for results |

### Bonus Points

- MCP server integration
- Additional custom tools (APIs, databases, web scraping)
- Streamlit or Gradio UI
- Real external integrations

---

## Example Flow

`example_flow.py` demonstrates all required patterns with a ticket triage system. **Study it, then build your own** — don't extend it.

Run it (requires a configured API key):

```bash
python example_flow.py
```

---

## Mock Data

Three datasets are provided in `mock_data/` for prototyping:

- **tickets.json** — Customer support tickets with message, channel, priority
- **agent_metrics.json** — Agent performance data (handle time, CSAT, FCR)
- **campaigns.json** — Marketing messages with target segments

Use these or bring your own data.

---

## Cheatsheet

See `docs/crewai_cheatsheet.md` for a quick reference on Flows, Agents, Tasks, Tools, Routers, and Pydantic output models.

---

## Support

Questions? Reach out on the challenge support channel provided by organizers.

---

*Built for the Konecta BPO Innovation Challenge*
