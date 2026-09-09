"""
Eco-Bridge -- ADK Orchestrator
"""

import os
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

from data_collection_agent import compute_footprint as _compute_footprint
from scoring_agent import compute_rubric_score as _compute_rubric_score


def get_sme_footprint(sme_id: str) -> dict:
    """Fetches an SME's real emissions footprint (Scope 2 grid + Scope 1/3 process
    emissions) from BigQuery, using sourced Carbonfact and CFE grid data.

    Args:
        sme_id: The SME's ID, e.g. 'SME0071'.

    Returns:
        A dict with material, location, production volume, and emissions breakdown.
    """
    return _compute_footprint(sme_id)


def get_compliance_score(sme_id: str) -> dict:
    """Computes a 0-100 sustainability compliance score for an SME, based on
    where their real emissions footprint falls between the best and worst
    real emission profiles found in the sourced Carbonfact + grid dataset.

    Args:
        sme_id: The SME's ID, e.g. 'SME0071'.

    Returns:
        A dict with the score and the best/worst-case bounds used to compute it.
    """
    footprint = _compute_footprint(sme_id)
    return _compute_rubric_score(footprint)


eco_bridge_agent = Agent(
    name="eco_bridge_agent",
    model="gemini-3.6-flash",
    description="Sustainability compliance auditor for textile SME manufacturers.",
    instruction="""
You are Eco-Bridge, a sustainability compliance assistant for small textile
manufacturers in India. When asked about an SME (by their sme_id, e.g.
'SME0071'), use your tools to fetch their real emissions data and compliance
score, then explain the result in plain language:
1. What their score means (they're compared against the best and worst real
   emission profiles found in our sourced dataset -- explain this honestly,
   don't overstate precision)
2. The single biggest driver of their emissions (compare Scope 2 grid
   emissions vs Scope 1/3 process emissions)
3. Two concrete, low-cost improvement suggestions suited to a small
   manufacturer, not a large factory

Keep your answer under 200 words, avoid jargon, and always call the tools
to get real numbers -- never estimate or make up emissions figures yourself.
""",
    tools=[get_sme_footprint, get_compliance_score],
)


def run_eco_bridge(sme_id: str) -> str:
    runner = InMemoryRunner(agent=eco_bridge_agent, app_name="eco_bridge")
    session = runner.session_service.create_session_sync(
        app_name="eco_bridge", user_id="demo_user"
    )

    query = f"Give me a full compliance report for {sme_id}."
    final_text = ""
    for event in runner.run(
        user_id="demo_user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=query)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    return final_text


if __name__ == "__main__":
    print(run_eco_bridge("SME0071"))
