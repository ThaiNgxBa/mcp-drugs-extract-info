import requests
import json
import os
from typing import List
from mcp.server.fastmcp import FastMCP

DRUG_DIR = "drugs"

# Initialize the FastMCP server
mcp = FastMCP("research")

@mcp.tool()
def search_drug_info(drug_name: str, max_results: int = 5) -> List[str]:
    """
    Search for drug information from openFDA by drug name (brand or substance).
    
    Args:
        drug_name (str): The name of the drug to search (e.g. 'ibuprofen')
        max_results (int): Number of results to fetch (default: 5)

    Returns:
        List[str]: A list of drug brand names found
    """

    # Prepare search query (brand_name OR substance_name)
    url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug_name}+openfda.substance_name:{drug_name}&limit={max_results}"

    # Send request
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return []

    data = response.json()
    results = data.get("results", [])

    # Create directory to store results
    path = os.path.join(DRUG_DIR, drug_name.lower().replace(" ", "_"))
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, "drug_info.json")

    # Collect drug information
    drug_info = {}
    brand_names = []

    for entry in results:
        openfda_data = entry.get("openfda", {})
        brand_name = openfda_data.get("brand_name", ["Unknown"])[0]
        substance = openfda_data.get("substance_name", ["Unknown"])[0]
        manufacturer = openfda_data.get("manufacturer_name", ["Unknown"])[0]
        route = openfda_data.get("route", ["Unknown"])[0]

        info = {
            "brand_name": brand_name,
            "substance_name": substance,
            "manufacturer": manufacturer,
            "route": route,
            "purpose": entry.get("purpose", ["Not specified"])[0],
            "usage": entry.get("indications_and_usage", ["Not specified"])[0],
            "warnings": entry.get("warnings", ["Not specified"])[0],
            "adverse_reactions": entry.get("adverse_reactions", ["Not specified"])[0],
            "boxed_warning": entry.get("boxed_warning", ["None"])[0]
        }

        drug_info[brand_name] = info
        brand_names.append(brand_name)

    # Save to file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(drug_info, f, indent=2, ensure_ascii=False)

    print(f"\n Drug info saved at: {file_path}")
    print("\n Found the following:")
    for name in brand_names:
        print(f"- {name}")
    
    return brand_names


@mcp.tool()
def extract_drug_info(brand_name: str) -> str:
    """
    Search for information about a specific drug by brand name across all drug_search directories.

    Args:
        brand_name (str): The brand name of the drug to look for

    Returns:
        str: JSON-formatted string with drug info if found, or an error message if not found
    """

    for folder in os.listdir("drugs"):
        folder_path = os.path.join("drugs", folder)
        if os.path.isdir(folder_path):
            file_path = os.path.join(folder_path, "drug_info.json")
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if brand_name in data:
                            return json.dumps(data[brand_name], indent=2, ensure_ascii=False)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"Error reading {file_path}: {str(e)}")
                    continue

    return f"No saved information found for drug brand: {brand_name}"

if __name__ == "__main__":
    mcp.run(transport='stdio')