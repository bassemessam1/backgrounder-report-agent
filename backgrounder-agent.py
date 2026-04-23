import argparse
import os
import re
from datetime import date
from typing import Type
from dotenv import load_dotenv

load_dotenv()

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from openai import OpenAI
from pydantic import BaseModel, Field

# --------------------------------------------------
# CUSTOM OPENAI NATIVE SEARCH TOOL
# --------------------------------------------------
class OpenAIWebSearchInput(BaseModel):
    query: str = Field(..., description="The web search query to run.")

class OpenAIWebSearchTool(BaseTool):
    name: str = "OpenAI Native Web Search"
    description: str = (
        "Search the web using OpenAI's native web_search tool via the Responses API. "
        "Use this for current facts, ownership, URLs, speed tiers, product pages, and verification."
    )
    args_schema: Type[BaseModel] = OpenAIWebSearchInput

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace and strip obvious markdown clutter."""
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _extract_urls(self, text: str) -> list[str]:
        """Extract and deduplicate URLs from model output."""
        urls = re.findall(r'https?://[^\s\]\)\}>"\'`]+', text)
        seen = set()
        unique_urls = []
        for url in urls:
            clean_url = url.rstrip(".,;)")
            if clean_url not in seen:
                seen.add(clean_url)
                unique_urls.append(clean_url)
        return unique_urls

    def _run(self, query: str) -> str:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=(
                "Search the web for the query below.\n"
                "Return:\n"
                "1. A concise factual summary\n"
                "2. The most relevant source URLs\n"
                "3. If the query asks to verify a URL, clearly say whether it appears valid and relevant\n\n"
                f"Query: {query}"
            )
        )

        text = self._clean_text(response.output_text)
        urls = self._extract_urls(text)

        # Keep the return format predictable for Crew agents
        if urls:
            formatted_urls = "\n".join(f"- {u}" for u in urls[:10])
            return f"{text}\n\nRelevant URLs:\n{formatted_urls}"

        return text


# 1. Initialize the OpenAI GPT-5 LLM
openai_llm = LLM(
    model="openai/gpt-5",
    temperature=1.0,
)

# 2. Initialize the OpenAI Native Search Tool
search_tool = OpenAIWebSearchTool()

# --------------------------------------------------
# AGENT 1: The Telecom Analyst (Generator)
# --------------------------------------------------
telecom_analyst = Agent(
    role='Senior Telecom Industry Analyst',
    goal='Research and draft a highly structured, fact-based report on ISPs in {country} focusing on {isps}.',
    backstory=(
        "You are a veteran telecommunications analyst specializing in residential broadband markets. "
        "You know how to navigate ISP websites, find technical network details, and structure "
        "complex data into clear, scannable reports. You prioritize facts and explicitly state "
        "if information is unavailable."
    ),
    verbose=True,
    allow_delegation=False,
    tools=[search_tool],
    llm=openai_llm
)

# --------------------------------------------------
# AGENT 2: The Fact-Checking Auditor (Validator)
# --------------------------------------------------
auditor = Agent(
    role='Strict Data Auditor and Fact-Checker',
    goal='Verify every claim, speed tier, and URL in the Analyst\'s draft. Correct any hallucinations.',
    backstory=(
        "You are a meticulous QA specialist for a top-tier consulting firm. Your job is to take drafted "
        "reports and rigorously test them. You use web searches to ensure that URLs provided do not lead "
        "to dead or irrelevant pages, that ownership structures are up to date, and that speed tiers reflect "
        "current market offerings. You do not generate new sections; you only fix and finalize the draft."
    ),
    verbose=True,
    allow_delegation=False,
    tools=[search_tool],
    llm=openai_llm
)

# --------------------------------------------------
# TASK 1: Drafting the Report
# --------------------------------------------------
draft_report = Task(
    description=(
        "Analyze Internet Service Providers (ISPs) in {country} and provide structured, fact-based "
        "insights for the following ISPs: {isps}.\n\n"
        "Instructions:\n"
        "- Focus on residential household internet.\n"
        "- Use the search tool to find current data.\n"
        "- Prefer official ISP websites and official company pages where possible.\n"
        "- If unavailable, explicitly state 'Not publicly available'.\n\n"
        "Format strictly as follows for EACH ISP:\n"
        "-------------------------------------\n"
        "ISP Name: [Name]\n"
        "1. Ownership: [Details]\n"
        "2. Customer-facing brand: [Brands/Regions]\n"
        "3. Fiber infrastructure: [Network/Technology]\n"
        "4. Fixed Wireless Access (FWA): [Yes/No, Tech, Target, URL]\n"
        "5. The FWA router: [Model, Specs, Home Router/MiFi, URL]\n"
        "6. Mobile network dependency: [Operator, Owned/MVNO, Router type, URL]\n"
        "7. Home fiber broadband offers: [Speeds, Differentiators, Flagship]\n"
        "-------------------------------------"
    ),
    expected_output="A complete, structured markdown report containing the drafted research for all specified ISPs.",
    agent=telecom_analyst
)

# --------------------------------------------------
# TASK 2: Validating the Report
# --------------------------------------------------
audit_report = Task(
    description=(
        "Review the draft report created by the Telecom Analyst.\n"
        "1. Extract every FWA and Mobile URL provided and use the search tool to verify the link exists and is relevant.\n"
        "2. Verify the 'Speed Tiers' and 'Ownership' claims by doing a quick cross-reference search.\n"
        "3. If any data is wrong, outdated, unsupported, or too vague, correct it.\n"
        "4. Keep only claims that are supportable from current web evidence.\n"
        "5. Ensure the final output perfectly matches the requested format.\n"
        "6. Output the final, corrected markdown report."
    ),
    expected_output="The final, verified markdown report, scrubbed of hallucinations and formatting errors.",
    agent=auditor
)

# --------------------------------------------------
# CREW: Putting it all together
# --------------------------------------------------
telecom_crew = Crew(
    agents=[telecom_analyst, auditor],
    tasks=[draft_report, audit_report],
    process=Process.sequential,
    verbose=True
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and audit a telecom ISP backgrounder report."
    )
    parser.add_argument(
        "--country",
        required=True,
        help="Target country for the report, for example: Italy",
    )
    parser.add_argument(
        "--isps",
        required=True,
        help="Comma-separated ISP names, for example: Sky, EOLO, Tiscali",
    )
    return parser.parse_args()

# --------------------------------------------------
# EXECUTION
# --------------------------------------------------
if __name__ == "__main__":
    args = parse_args()
    report_inputs = {
        'country': args.country.strip(),
        'isps': args.isps.strip(),
    }

    print("Starting the multi-agent telecom research process...\n")
    final_result = telecom_crew.kickoff(inputs=report_inputs)

    print("\n================================================")
    print("FINAL VERIFIED REPORT:")
    print("================================================\n")
    print(final_result)

    # Save the report as markdown using country + date in the file name.
    country_value = report_inputs.get('country', 'report')
    country_slug = re.sub(r'[^A-Za-z0-9]+', '-', country_value.strip()).strip('-').lower() or 'report'
    report_date = date.today().isoformat()
    output_filename = f"Backgrounder_{country_slug}_{report_date}.md"

    with open(output_filename, "w", encoding="utf-8") as report_file:
        report_file.write(str(final_result))

    print(f"\nReport saved to: {output_filename}")