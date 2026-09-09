"""
Eco-Bridge -- Data Collection Agent (v3)
Matches the actual table/column names in the ECO_CC BigQuery dataset.

Prerequisite: pip install google-cloud-bigquery pandas --break-system-packages
Auth: gcloud auth application-default login (already done in Cloud Shell)
"""

from google.cloud import bigquery

PROJECT_ID = "project-8c1c81c2-77cc-4e29-a70"
DATASET_ID = "ECO_CC"

SME_TABLE = "TEXTILE_SYN"
FACTORS_TABLE = "CARB_CC"
GRID_TABLE = "EC"
BENCHMARK_TABLE = "plastic"

DEFAULT_GRID_INTENSITY = 640  # fallback for locations not in the EC table (most Indian towns besides Mumbai/Delhi)

client = bigquery.Client(project=PROJECT_ID)


def get_sme_record(sme_id: str) -> dict:
    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.{SME_TABLE}`
        WHERE sme_id = @sme_id
        LIMIT 1
    """
    job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("sme_id", "STRING", sme_id)]
    ))
    rows = list(job.result())
    if not rows:
        raise ValueError(f"No SME record found for sme_id: {sme_id}")
    return dict(rows[0])


def get_process_factor(material: str) -> float:
    """CARB_CC's material-name column loaded as 'string_field_0' (no header detected)."""
    query = f"""
        SELECT total_process_ghg_kg_per_kg
        FROM `{PROJECT_ID}.{DATASET_ID}.{FACTORS_TABLE}`
        WHERE LOWER(string_field_0) = LOWER(@material)
        LIMIT 1
    """
    job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("material", "STRING", material)]
    ))
    rows = list(job.result())
    if not rows:
        raise ValueError(f"No process factor found for material: {material}")
    return rows[0].total_process_ghg_kg_per_kg


def get_grid_intensity(location: str, year: int = 2023) -> float:
    query = f"""
        SELECT grid_carbon_intensity
        FROM `{PROJECT_ID}.{DATASET_ID}.{GRID_TABLE}`
        WHERE LOWER(location) = LOWER(@location) AND year = @year
        LIMIT 1
    """
    job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("location", "STRING", location),
            bigquery.ScalarQueryParameter("year", "INT64", year),
        ]
    ))
    rows = list(job.result())
    if rows:
        return rows[0].grid_carbon_intensity
    return DEFAULT_GRID_INTENSITY  # fallback -- most SME towns (Jetpur, Tirupur, etc.) aren't in this dataset


# The 'plastic' (buyer benchmark) table only has these Product_Type values:
# Polyester, Nylon, Recycled_Poly, Cotton, Synthetic_Blend, Organic_Cotton,
# Microfiber, Linen, Tencel, Viscose, Wool.
# Fabric-name materials in TEXTILE_SYN (Chiffon, Georgette, Satin, Velvet, Lace,
# Denim, Pashmina, Leather, Faux Leather) don't appear directly -- map each to
# its closest matching brand-reported category.
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
    "Leather": "Synthetic_Blend",       # no leather category in this dataset -- closest proxy
    "Faux Leather": "Synthetic_Blend",  # same
}


def get_buyer_benchmark(material_or_product_type: str) -> dict:
    lookup_material = BENCHMARK_MATERIAL_MAP.get(material_or_product_type, material_or_product_type)
    query = f"""
        SELECT
            AVG(Greenhouse_Gas_Emissions) AS avg_ghg,
            AVG(Water_Consumption) AS avg_water,
            AVG(Energy_Consumption) AS avg_energy,
            AVG(Waste_Generation) AS avg_waste
        FROM `{PROJECT_ID}.{DATASET_ID}.{BENCHMARK_TABLE}`
        WHERE LOWER(Product_Type) = LOWER(@material)
    """
    job = client.query(query, job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("material", "STRING", lookup_material)]
    ))
    rows = list(job.result())
    result = dict(rows[0]) if rows else {}
    result["_benchmark_material_used"] = lookup_material  # transparency: shows which proxy category was used
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
