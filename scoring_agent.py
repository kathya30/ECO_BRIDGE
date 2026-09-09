"""
Eco-Bridge -- Compliance Scoring Agent (v3)
Scoring now uses REAL, sourced best/worst-case bounds (from your own
Carbonfact + CFE data) instead of an unverified brand-benchmark ratio.
The buyer benchmark is still shown for context, but no longer drives the score.
"""

import os
from google import genai
from data_collection_agent import compute_footprint

client_ai = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_NAME = "gemini-3.6-flash"

BEST_PROCESS_FACTOR = 15.580892
WORST_PROCESS_FACTOR = 30.633595
BEST_GRID_G_PER_KWH = 0
WORST_GRID_G_PER_KWH = 752


def compute_rubric_score(footprint: dict) -> dict:
    production_kg = footprint["monthly_production_kg"]
    total_ghg = footprint["total_ghg_kgco2e"]

    if not production_kg:
        return {"score": None, "reason": "Missing production data."}

    actual_ghg_per_kg = total_ghg / production_kg

    energy_kwh_actual = footprint["scope2_ghg_kgco2e"] * 1000 / footprint.get("grid_intensity_used_g_per_kwh", 640)

    best_case_total = production_kg * BEST_PROCESS_FACTOR + energy_kwh_actual * BEST_GRID_G_PER_KWH / 1000
    worst_case_total = production_kg * WORST_PROCESS_FACTOR + energy_kwh_actual * WORST_GRID_G_PER_KWH / 1000

    best_case_per_kg = best_case_total / production_kg
    worst_case_per_kg = worst_case_total / production_kg

    if worst_case_per_kg == best_case_per_kg:
        score = 100
    else:
        raw_score = 100 * (worst_case_per_kg - actual_ghg_per_kg) / (worst_case_per_kg - best_case_per_kg)
        score = max(0, min(100, round(raw_score)))

    return {
        "score": score,
        "actual_ghg_per_kg": round(actual_ghg_per_kg, 3),
        "best_case_ghg_per_kg": round(best_case_per_kg, 3),
        "worst_case_ghg_per_kg": round(worst_case_per_kg, 3),
    }


def generate_explanation(footprint: dict, rubric: dict) -> str:
    prompt = f"""
You are a sustainability compliance analyst writing a short report section for a small
textile manufacturer (SME) in India, explaining their emissions compliance score to
help them understand it and improve.

SME data:
- Material: {footprint['material']}
- Location: {footprint['location']}
- Monthly production: {footprint['monthly_production_kg']} kg
- Scope 2 (grid electricity) emissions: {footprint['scope2_ghg_kgco2e']} kgCO2e
- Scope 1/3 (process) emissions: {footprint['scope1_3_ghg_kgco2e']} kgCO2e
- Total emissions: {footprint['total_ghg_kgco2e']} kgCO2e
- Compliance score: {rubric['score']}/100
- Their actual per-kg footprint: {rubric.get('actual_ghg_per_kg')} kgCO2e/kg
- Best-case per-kg footprint achievable (cleanest process + grid in our dataset): {rubric.get('best_case_ghg_per_kg')} kgCO2e/kg
- Worst-case per-kg footprint (least efficient process + dirtiest grid in our dataset): {rubric.get('worst_case_ghg_per_kg')} kgCO2e/kg

Write 3 short paragraphs:
1. Plain-language summary of what this score means (no jargon), referencing where they sit between best and worst case
2. The single biggest driver of their emissions (Scope 2 vs process emissions -- compare the two numbers)
3. Two concrete, specific, low-cost improvement suggestions for a small manufacturer

Keep it under 200 words total. Write for someone who is not a sustainability expert.
"""
    response = client_ai.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text


def score_sme(sme_id: str) -> dict:
    footprint = compute_footprint(sme_id)
    rubric = compute_rubric_score(footprint)
    explanation = generate_explanation(footprint, rubric) if rubric["score"] is not None else "Not enough data to generate a report."

    return {
        "footprint": footprint,
        "rubric": rubric,
        "explanation": explanation,
    }


if __name__ == "__main__":
    result = score_sme("SME0071")
    print("SCORE:", result["rubric"]["score"], "/100")
    print("Actual:", result["rubric"]["actual_ghg_per_kg"], "kgCO2e/kg")
    print("Best case:", result["rubric"]["best_case_ghg_per_kg"], "kgCO2e/kg")
    print("Worst case:", result["rubric"]["worst_case_ghg_per_kg"], "kgCO2e/kg")
    print()
    print("EXPLANATION:")
    print(result["explanation"])
