# Backgrounder Reports Agent

A small CrewAI project that generates a telecom ISP backgrounder report and then audits it for factual consistency.

## What This Project Does

The script runs a 2-agent pipeline to produce a structured ISP report for a target country:

1. Researches and drafts the report.
2. Audits and corrects the draft (URLs, ownership, speed tiers, and formatting).

The report is printed in the terminal and saved to a markdown file named like:

- `Backgrounder_<country>_<YYYY-MM-DD>.md`

Example:

- `Backgrounder_italy_2026-04-22.md`

## Agents

### 1) Senior Telecom Industry Analyst (Generator)

Responsibilities:

- Research residential broadband information for specified ISPs.
- Collect ownership, brand, fiber, FWA, router, mobile dependency, and offers.
- Produce a structured draft in a strict per-ISP format.

### 2) Strict Data Auditor and Fact-Checker (Validator)

Responsibilities:

- Verify FWA/mobile URLs and claim validity.
- Cross-check ownership and speed tier claims.
- Remove or fix unsupported information.
- Output a cleaned, final markdown report.

## Tooling

The script defines a custom CrewAI tool:

- `OpenAI Native Web Search`
  - Uses OpenAI Responses API with `web_search`.
  - Returns a concise summary and relevant source URLs.

## Requirements

Python:

- Python 3.10+

Python packages used by `backgrounder-agent.py`:

- `crewai`
- `openai`
- `python-dotenv`
- `pydantic`

Environment variables:

- `OPENAI_API_KEY` (required)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Add your API key to `.env`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_api_key_here
```

## How To Run

From the project root:

```bash
source .venv/bin/activate
python backgrounder-agent.py
```

## Current Default Inputs

Inside `backgrounder-agent.py`, defaults are:

- Country: `Italy`
- ISPs: `Sky, EOLO, Tiscali, Iliad, Digi, Dimensione`

To change the target country or ISP list, edit the `report_inputs` dictionary in the `__main__` block.

## Output

When execution completes:

- Final verified report is printed to terminal.
- A markdown file is generated in the project root:
  - `Backgrounder_<country-slug>_<today-date>.md`

## Notes

- The process is sequential: draft first, then audit.
- If data cannot be found, agents are instructed to mark it as not publicly available.
- Results depend on live web availability and current source pages.
