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

@mcp.resource("drugs://categories")
def get_available_drug_categories() -> str:
    """
    List all available drug categories (substance folders) in the drugs directory.
    
    This resource provides a simple list of all available drug categories based on 
    substance names that have been searched and saved.
    """
    categories = []
    
    # Get all drug directories
    if os.path.exists(DRUG_DIR):
        for drug_dir in os.listdir(DRUG_DIR):
            drug_path = os.path.join(DRUG_DIR, drug_dir)
            if os.path.isdir(drug_path):
                drug_file = os.path.join(drug_path, "drug_info.json")
                if os.path.exists(drug_file):
                    categories.append(drug_dir)
    
    # Create a simple markdown list
    content = "# Available Drug Categories\n\n"
    if categories:
        content += f"**Total Categories**: {len(categories)}\n\n"
        for category in sorted(categories):
            content += f"- **{category.replace('_', ' ').title()}**\n"
        content += f"\nUse the drug category name with other tools to access detailed information.\n"
    else:
        content += "No drug categories found. Search for drugs first using `search_drug_info()`.\n"
    
    return content

@mcp.resource("drugs://{category}")
def get_category_drugs(category: str) -> str:
    """
    Get detailed information about all drugs in a specific category.
    
    Args:
        category: The drug category (substance name) to retrieve information for
    """
    category_dir = category.lower().replace(" ", "_")
    drug_file = os.path.join(DRUG_DIR, category_dir, "drug_info.json")
    
    if not os.path.exists(drug_file):
        return f"# No drugs found for category: {category}\n\nTry searching for drugs in this category first using `search_drug_info('{category}')`."
    
    try:
        with open(drug_file, 'r', encoding='utf-8') as f:
            drugs_data = json.load(f)
        
        # Create markdown content with drug details
        content = f"# Drugs in Category: {category.replace('_', ' ').title()}\n\n"
        content += f"**Total Products**: {len(drugs_data)}\n\n"
        
        for brand_name, drug_info in drugs_data.items():
            content += f"## {brand_name}\n"
            content += f"- **Substance**: {drug_info['substance_name']}\n"
            content += f"- **Manufacturer**: {drug_info['manufacturer']}\n"
            content += f"- **Route**: {drug_info['route']}\n"
            content += f"- **Purpose**: {drug_info['purpose']}\n\n"
            
            # Usage section
            if drug_info['usage'] != "Not specified":
                content += f"### Usage\n{drug_info['usage'][:300]}{'...' if len(drug_info['usage']) > 300 else ''}\n\n"
            
            # Warnings section (abbreviated)
            if drug_info['warnings'] != "Not specified":
                content += f"### Key Warnings\n{drug_info['warnings'][:200]}{'...' if len(drug_info['warnings']) > 200 else ''}\n\n"
            
            # Boxed warning if present
            if drug_info['boxed_warning'] != "None":
                content += f"### ⚠️ Boxed Warning\n{drug_info['boxed_warning'][:200]}{'...' if len(drug_info['boxed_warning']) > 200 else ''}\n\n"
            
            content += "---\n\n"
        
        return content
    except json.JSONDecodeError:
        return f"# Error reading drug data for {category}\n\nThe drug data file is corrupted."

@mcp.prompt()
def generate_drug_research_prompt(substance_name: str, research_focus: str = "general") -> str:
    """
    Generate a comprehensive research prompt for drug analysis.
    
    Args:
        substance_name (str): The drug substance to research
        research_focus (str): Focus area - 'safety', 'efficacy', 'interactions', or 'general'
    """
    
    focus_instructions = {
        "safety": "Focus on safety profiles, adverse reactions, contraindications, and risk factors",
        "efficacy": "Focus on therapeutic effectiveness, clinical outcomes, and comparative efficacy", 
        "interactions": "Focus on drug-drug interactions, food interactions, and contraindications",
        "general": "Provide comprehensive overview including safety, efficacy, and clinical considerations"
    }
    
    instruction = focus_instructions.get(research_focus, focus_instructions["general"])
    
    return f"""Conduct comprehensive drug research analysis for '{substance_name}' with focus on {research_focus}. Follow these steps:

1. **Initial Data Collection**
   - Use search_drug_info('{substance_name}') to gather FDA label data
   - Extract key information using extract_drug_info() for specific products

2. **Comparative Analysis** 
   - Use compare_drugs_in_category('{substance_name}') to analyze different formulations
   - Identify patterns across manufacturers and formulations

3. **Safety Assessment**
   - Use get_drug_safety_summary('{substance_name}') for safety profile
   - {instruction}

4. **Research Synthesis**
   Provide a structured analysis including:
   - **Overview**: What is {substance_name} and its primary uses
   - **Available Formulations**: Different brands and manufacturers
   - **Safety Profile**: Key warnings, contraindications, adverse reactions
   - **Clinical Considerations**: Important prescribing information
   - **Comparative Notes**: Differences between available products
   - **Research Gaps**: Areas needing further investigation

5. **Format Requirements**
   - Use clear headings and bullet points
   - Highlight critical safety information
   - Include specific product names when relevant
   - Cite FDA label data sources

Focus Area: {instruction}

Begin your analysis with the data collection steps above."""

if __name__ == "__main__":
    mcp.run(transport='stdio')