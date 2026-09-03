#!/usr/bin/env python3
"""
ChainWatch — Map Fetcher & Preprocessor
Downloads the India TopoJSON, normalizes state names to match the ML model,
and saves it directly to the frontend folder for 100% offline use.
"""

import urllib.request
import json
import os

MAP_URL = "https://cdn.jsdelivr.net/gh/udit-001/india-maps-data@2884453/topojson/india.json"

# Assuming backend and frontend are side-by-side in your main folder
FRONTEND_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chainwatch_frontend", "src"))
OUTPUT_FILE = os.path.join(FRONTEND_SRC_DIR, "india-states.json")

# Mapping to ensure the map's state names perfectly match our ML Python generator
NAME_CORRECTIONS = {
    "NCT of Delhi": "Delhi",
    "Andaman & Nicobar Island": "Andaman and Nicobar Islands",
    "Arunanchal Pradesh": "Arunachal Pradesh",
    "Dadara & Nagar Havelli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman & Diu": "Dadra and Nagar Haveli and Daman and Diu",
}

def fetch_and_process_map():
    print(f"⏳ Downloading map data from: {MAP_URL}")
    
    try:
        # 1. Fetch the JSON
        with urllib.request.urlopen(MAP_URL) as response:
            data = json.loads(response.read().decode())
        
        print("✅ Download successful. Preprocessing state names...")
        
        # 2. Preprocess the TopoJSON to normalize state names
        # TopoJSON stores the states inside objects -> india -> geometries
        if "objects" in data and "india" in data["objects"]:
            geometries = data["objects"]["india"]["geometries"]
            
            for geo in geometries:
                props = geo.get("properties", {})
                
                # Check different possible keys for the state name
                current_name = props.get("st_nm") or props.get("name") or props.get("NAME_1")
                
                if current_name in NAME_CORRECTIONS:
                    corrected = NAME_CORRECTIONS[current_name]
                    print(f"   Fixing: '{current_name}' -> '{corrected}'")
                    # Force update all possible keys so React finds it easily
                    props["st_nm"] = corrected
                    props["name"] = corrected
                    props["NAME_1"] = corrected
                    
        # 3. Ensure frontend src directory exists
        if not os.path.exists(FRONTEND_SRC_DIR):
            print(f"❌ Error: Frontend directory not found at {FRONTEND_SRC_DIR}")
            print("Make sure your backend and frontend folders are next to each other!")
            return

        # 4. Save to frontend folder
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            
        print(f"✅ Map successfully preprocessed and saved to:\n   {OUTPUT_FILE}")
        print("🚀 Your React frontend is now 100% offline-ready!")

    except Exception as e:
        print(f"❌ Failed to fetch or process map: {e}")

if __name__ == "__main__":
    fetch_and_process_map()