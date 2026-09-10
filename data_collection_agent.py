"""
Eco-Bridge -- Data Collection Agent (v5, CSV-based)
Reads from local CSV files bundled in the repo instead of live BigQuery
queries. This removes all cloud-auth complexity for deployment (no service
account, no billing dependency) while using the exact same sourced data.
CSV files live in the data/ folder: TEXTILE_SYN.csv, CARB_CC.csv, EC.csv, plastic.csv
"""

import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

DEFAULT_GRID_INTENSITY = 640

_sme_df = pd.read_csv(os.path.join(DATA_DIR, "TEXTILE_SYN.csv"))
_factors_df = pd.read_csv(os.path.join(DATA_DIR, "CARB_CC.csv"))
_factors_df = _factors_df.rename(columns={_factors_df.columns[0]: "material"})
_grid_df = pd.read_csv(os.path.join(DATA_DIR, "EC.csv"))
_benchmark_df = pd.read_csv(os.path.join(DATA_DIR, "plastic.csv"))


def get_sme_record(sme_id: str) -> dict:
    match = _sme_df[_sme_df["sme_id"] == sme_id]
    if match.empty:
        raise ValueError(f"No SME record found for sme_id: {sme_id}")
    return match.iloc[0].to_dict()


def get_process_factor(material: str) -> float:
    match = _factors_df[_factors_df["material"].str.lower() == material.lower()]
    if match.empty:
        raise ValueError(f"No process factor found for material: {material}")
    return float(match.iloc[0]["total_process_ghg_kg_per_kg"])


def get_grid_intensity(location: str, year: int = 2023) -> float:
    match = _grid_df[
        (_grid_df["location"].str.lower() == location.lower()) & (_grid_df["year"] == year)
    ]
    if not match.empty and pd.notna(match.iloc[0]["grid_carbon_intensity"]):
        return float(match.iloc[0]["grid_carbon_intensity"])
    return DEFAULT_GRID_INTENSITY


BENCHMARK_MATERIAL_MAP = {
    "Chiffon": "Synthetic_Blend",
    "Georgette": "Synthetic_Blend",
    "Satin": "Synthetic_Blend",
    "Velvet": "Synthetic_Blend",
    "Lace": "Nylon",
    "Denim": "Cotton",
    "Pashmina": "Wool",
    "Rayon": "Viscose",
    "Lycra": "Synthetic_Blend",
    "Spandex": "Synthetic_Blend",
    "Leather": "Synthetic_Blend",
    "Faux Leather": "Synthetic_Blend",
}


def get_buyer_benchmark(material_or_product_type: str) -> dict:
    lookup_material = BENCHMARK_MATERIAL_MAP.get(material_or_product_type, material_or_product_type)
    match = _benchmark_df[_benchmark_df["Product_Type"].str.lower() == lookup_material.lower()]
    if match.empty:
        result = {"avg_ghg": None, "avg_water": None, "avg_energy": None, "avg_waste": None}
    else:
        result = {
            "avg_ghg": float(match["Greenhouse_Gas_Emissions"].mean()),
            "avg_water": float(match["Water_Consumption"].mean()),
            "avg_energy": float(match["Energy_Consumption"].mean()),
            "avg_waste": float(match["Waste_Generation"].mean()),
        }
    result["_benchmark_material_used"] = lookup_material
    return result


def compute_footprint(sme_id: str) -> dict:
    record = get_sme_record(sme_id)
    material = record["material"]
    location = record["location"]
    production_kg = record["monthly_production_kg"]
    energy_kwh = record["energy_consumption_kwh"]

    grid_intensity = get_grid_intensity(location)
    scope2 = energy_kwh * grid_intensity / 1000

    process_factor = get_process_factor(material)
    scope1_3 = production_kg * process_factor

    benchmark = get_buyer_benchmark(material)

    return {
        "sme_id": sme_id,
        "material": material,
        "location": location,
        "monthly_production_kg": production_kg,
        "grid_intensity_used_g_per_kwh": grid_intensity,
        "scope2_ghg_kgco2e": round(scope2, 2),
        "scope1_3_ghg_kgco2e": round(scope1_3, 2),
        "total_ghg_kgco2e": round(scope2 + scope1_3, 2),
        "process_factor_used_kg_per_kg": round(process_factor, 3),
        "buyer_benchmark": benchmark,
    }


if __name__ == "__main__":
    result = compute_footprint("SME0071")
    print(result)
