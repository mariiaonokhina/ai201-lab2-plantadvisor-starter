import json
import os
from datetime import datetime
from config import DATA_PATH
import difflib  # For close matching

# Function to normalize strings for matching by converting to lowercase
# and stripping whitespace 
def _normalize(s: str) -> str:
    return s.strip().lower()

# Plant database and seasonal data are loaded once at module load.
# This mirrors how a real service would cache its data source in memory.
with open(os.path.join(DATA_PATH, "plants.json"), encoding="utf-8") as f:
    _plant_db = json.load(f)

# The name index dictionary is built once and reused for every query.
# For each plant, register the slug, the slug with underscores→spaces, 
# the display_name, the scientific_name, and every alias
def _build_name_index(plant_db: dict) -> dict:
    index = {}
    for slug, data in plant_db.items():
        index[_normalize(slug)] = slug
        index[_normalize(slug.replace("_", " "))] = slug
        index[_normalize(data["display_name"])] = slug
        if "scientific_name" in data:
            index[_normalize(data["scientific_name"])] = slug
        for alias in data.get("aliases", []):
            index[_normalize(alias)] = slug
    return index

_NAME_INDEX = _build_name_index(_plant_db)

with open(os.path.join(DATA_PATH, "seasons.json"), encoding="utf-8") as f:
    _season_data = json.load(f)

# Maps calendar months to seasons for auto-detection.
_MONTH_TO_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "fall",  10: "fall",  11: "fall",
}


def lookup_plant(plant_name: str) -> dict:
    """
    Search the plant database for a plant by name and return its care information.

    The plant database (_plant_db) is a dict where keys are lowercase slugs like
    "pothos", "snake_plant", "fiddle_leaf_fig". Each plant also has a "display_name"
    field and an "aliases" list with common alternate names.

    All matching is case-insensitive. Stripped whitespace from the input.

    Return format when found:
      {"found": True, "plant": <the full plant dict>}

    Return format when not found:
      {"found": False, "name": <original input>, "message": <helpful string>}
    """
    normalized = _normalize(plant_name)

    # O(1) lookup across keys, display names, scientific names, and aliases
    slug = _NAME_INDEX.get(normalized)
    if slug is not None:
        return {"found": True, "plant": _plant_db[slug]}

    # Not found — compute close matches in case of a spelling error
    closest_keys = difflib.get_close_matches(
        normalized, _NAME_INDEX.keys(), n=3, cutoff=0.6
    )
    # Map matched index keys back to display names (dedup, preserve order)
    closest_matches = list(dict.fromkeys(
        _plant_db[_NAME_INDEX[k]]["display_name"] for k in closest_keys
    ))
    available_plants = sorted(
        data["display_name"] for data in _plant_db.values()
    )

    if closest_matches:
        message = (
            f"There is no exact match in the database for {plant_name}. "
            f"This may be a spelling error. The closest matches in the database: "
            f"{closest_matches}. Ask the user if they meant one of these before answering."
        )
    else:
        message = (
            f"There is no exact match in the database for {plant_name}. "
            f"Available plants: {available_plants}. Tell the user this plant is not "
            f"in the database, suggest one of the available plants, and offer general "
            f"care advice if appropriate, but do not invent plant-specific care details."
        )

    return {"found": False, "name": plant_name, "message": message}


def get_seasonal_conditions(season: str | None = None) -> dict:
    """
    Return current seasonal care context for houseplants.

    If season is provided and valid, returns that season's data.
    If season is None (or invalid), auto-detects from the current calendar month.

    Pre-implemented — read through this and the spec before working on lookup_plant().
    """
    VALID_SEASONS = {"spring", "summer", "fall", "winter"}

    if season and season.lower() in VALID_SEASONS:
        # Caller specified a valid season — use it directly
        season_key = season.lower()
        detected = False
    else:
        # Auto-detect from the current month using the _MONTH_TO_SEASON mapping
        current_month = datetime.now().month
        season_key = _MONTH_TO_SEASON[current_month]
        detected = True

    # Copy the season dict so we don't mutate the cached data
    result = dict(_season_data[season_key])
    result["detected_season"] = detected
    return result
