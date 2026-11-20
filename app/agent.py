# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Any, Dict, List
import uuid
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.tool_context import ToolContext
from google.cloud import firestore, storage
from google import genai
from google.genai import types
try:
    from a2ui.schema.manager import A2uiSchemaManager
    from a2ui.basic_catalog.provider import BasicCatalog
except ImportError:
    A2uiSchemaManager = None
    BasicCatalog = None
from .a2ui_utils import a2ui_callback

MODEL = "gemini-3.8-flash"
FIRESTORE_PROJECT = "qwiklabs-gcp-04-91797115bb4a"
GCS_BUCKET_NAME = "chefpal-dishes-qwiklabs-gcp-04-91797115bb4a"

# Initialize Firestore client with hardcoded project ID
db = firestore.Client(project=FIRESTORE_PROJECT)
# Initialize Cloud Storage client
storage_client = storage.Client(project=FIRESTORE_PROJECT)


def list_pantry_items() -> List[Dict[str, Any]]:
    """Retrieves all current ingredients and items available in the user's pantry.

    Returns:
        A list of items in the pantry with their name, quantity, unit, and category.
    """
    items = []
    docs = db.collection("pantry_items").stream()
    for doc in docs:
        data = doc.to_dict()
        items.append(data)
    return items


def update_pantry_item(name: str, quantity: float, unit: str, category: str = "general", notes: str = "") -> str:
    """Adds or updates an ingredient in the user's pantry inventory.

    Args:
        name: The name of the ingredient (e.g. 'Eggs', 'Milk', 'Olive Oil').
        quantity: The numeric quantity available.
        unit: The unit of measurement (e.g. 'pieces', 'grams', 'liter', 'ml').
        category: The category (e.g. 'dairy', 'produce', 'spices', 'grains').
        notes: Optional extra notes (e.g. 'organic', 'keep in fridge').

    Returns:
        A confirmation message indicating the item was updated or added.
    """
    doc_id = name.lower().replace(" ", "_").strip()
    item_data = {
        "id": doc_id,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "category": category,
        "notes": notes,
    }
    db.collection("pantry_items").document(doc_id).set(item_data)
    return f"Successfully updated pantry: {name} ({quantity} {unit})."


def search_recipes(cuisine: str = "") -> List[Dict[str, Any]]:
    """Searches available recipes in the database, optionally filtered by cuisine.

    Args:
        cuisine: Optional cuisine type to filter by (e.g., 'Italian', 'Mexican'). If empty, returns all.

    Returns:
        A list of recipe details including ingredients and instructions.
    """
    recipes = []
    col = db.collection("recipes")
    docs = col.stream()
    for doc in docs:
        data = doc.to_dict()
        if cuisine:
            if cuisine.lower() in data.get("cuisine", "").lower():
                recipes.append(data)
        else:
            recipes.append(data)
    return recipes


def scale_recipe_ingredients(recipe_id: str, target_servings: int) -> Dict[str, Any]:
    """Scales the ingredient quantities of a recipe to a desired number of servings.

    Args:
        recipe_id: The ID of the recipe to scale (e.g., 'classic_carbonara', 'garlic_olive_oil_pasta').
        target_servings: The desired number of servings to scale for.

    Returns:
        A dictionary with the recipe title, original servings, target servings, scale ratio, and scaled ingredient descriptions.
    """
    doc = db.collection("recipes").document(recipe_id).get()
    if not doc.exists:
        return {"error": f"Recipe '{recipe_id}' not found."}

    data = doc.to_dict()
    original_servings = data.get("servings", 1) or 1
    ratio = target_servings / original_servings

    return {
        "recipe_title": data.get("title", recipe_id),
        "original_servings": original_servings,
        "target_servings": target_servings,
        "scale_ratio": round(ratio, 2),
        "original_ingredients": data.get("ingredients", []),
        "scaling_note": f"Multiply each ingredient amount by {round(ratio, 2)}x (from {original_servings} to {target_servings} servings)."
    }


def fetch_online_recipes(query: str) -> List[Dict[str, Any]]:
    """Fetches real-world recipe details from the free public TheMealDB API.

    Args:
        query: The dish name or main ingredient to search for (e.g., 'Arrabiata', 'Chicken', 'Salmon').

    Returns:
        A list of matching recipe details including dish name, category, cuisine area, instructions, and ingredients.
    """
    import urllib.request
    import json

    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChefPalAgent/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return [{"error": f"Failed to fetch online recipes: {str(e)}"}]

    meals = data.get("meals")
    if not meals:
        return [{"message": f"No online recipes found matching '{query}'."}]

    results = []
    for m in meals[:3]:  # Return top 3 matches to keep context compact
        # Parse ingredients and measures
        ingredients = []
        for i in range(1, 21):
            ing = m.get(f"strIngredient{i}")
            measure = m.get(f"strMeasure{i}")
            if ing and ing.strip():
                measure_str = f" ({measure.strip()})" if measure and measure.strip() else ""
                ingredients.append(f"{ing.strip()}{measure_str}")

        results.append({
            "meal_id": m.get("idMeal"),
            "title": m.get("strMeal"),
            "category": m.get("strCategory"),
            "area": m.get("strArea"),
            "instructions": m.get("strInstructions", "")[:400] + "...",
            "ingredients": ingredients,
            "thumbnail_url": m.get("strMealThumb"),
        })

    return results


def geocode_address(address: str) -> Dict[str, Any]:
    """Converts a street address or city name into geographic coordinates (latitude and longitude) using Google Geocoding API.

    Args:
        address: The address or place name to geocode (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A dictionary with the formatted address, latitude, and longitude.
    """
    import os
    import urllib.request
    import json

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChefPalAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": f"Failed to call Geocoding API: {str(e)}"}

    if data.get("status") != "OK" or not data.get("results"):
        return {"error": f"Geocoding failed with status: {data.get('status')}"}

    result = data["results"][0]
    loc = result.get("geometry", {}).get("location", {})
    return {
        "formatted_address": result.get("formatted_address"),
        "latitude": loc.get("lat"),
        "longitude": loc.get("lng"),
    }


def find_nearby_places(latitude: float, longitude: float, place_type: str = "supermarket", radius_meters: float = 5000.0) -> List[Dict[str, Any]]:
    """Finds nearby places of a given type around specific coordinates using Google Places API (New).

    Args:
        latitude: The latitude of the center search point.
        longitude: The longitude of the center search point.
        place_type: Type of place to search for (e.g., 'supermarket', 'grocery_store', 'bakery', 'restaurant').
        radius_meters: Search radius in meters (default is 5000 meters / 5km).

    Returns:
        A list of nearby places with their display name, formatted address, and location coordinates.
    """
    import os
    import urllib.request
    import json

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        "User-Agent": "ChefPalAgent/1.0",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return [{"error": f"Failed to call Places API: {str(e)}"}]

    places = data.get("places", [])
    if not places:
        return [{"message": f"No places of type '{place_type}' found within {radius_meters}m."}]

    results = []
    for p in places:
        name_obj = p.get("displayName", {})
        results.append({
            "name": name_obj.get("text", "Unknown"),
            "address": p.get("formattedAddress"),
            "location": p.get("location"),
        })
    return results


def generate_dish_image(dish_description: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Generates a high quality photorealistic image of a culinary dish or recipe concept using gemini-3.1-flash-lite-image.

    Saves the image as a session artifact and uploads it to a public Google Cloud Storage bucket.

    Args:
        dish_description: A description of the dish to illustrate (e.g., 'Spaghetti carbonara with creamy egg sauce and crispy pancetta').
        tool_context: The ADK tool context providing artifact storage for the current session.

    Returns:
        A dictionary containing the public image URL, filename, and status message.
    """
    try:
        # Initialize Gemini Client for Vertex AI in the global region
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
        prompt = f"Professional food photography of {dish_description}, award winning culinary plating, 4k, delicious, appetizing, warm studio lighting"
        
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            return {"error": "No image data was generated by the model."}

        # 1. Save artifact with tool_context so it appears in the Playground's Artifacts panel
        filename = f"dish_{uuid.uuid4().hex[:8]}.jpg"
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        save_res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
        import inspect
        if inspect.isawaitable(save_res):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(save_res)
                else:
                    loop.run_until_complete(save_res)
            except Exception:
                pass

        # 2. Upload the same image bytes to the public Cloud Storage bucket
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "message": f"Generated image for '{dish_description}'.",
            "image_url": public_url,
            "filename": filename,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload dish image: {str(e)}"}


def generate_dish_video(dish_description: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Generates a short culinary video for a dish or recipe concept using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the video as a session artifact and uploads it to the public Google Cloud Storage bucket.

    Args:
        dish_description: Description of the culinary dish or cooking technique to visualize as a video (e.g. 'A sizzling steak with rosemary butter baste').
        tool_context: The ADK tool context providing artifact storage for the current session.

    Returns:
        A dictionary containing the public video URL, filename, and status message.
    """
    import base64

    try:
        # Initialize Gemini Client for Vertex AI in the global region
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
        prompt = f"Professional culinary food video of {dish_description}, continuous smooth motion, 4k cinematic presentation, appetizing lighting."

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        output_video = getattr(interaction, "output_video", None)
        if not output_video or not getattr(output_video, "data", None):
            return {"error": "No video data was returned by the Omni model."}

        # Decode video bytes from base64 string
        video_data = output_video.data
        if isinstance(video_data, str):
            video_bytes = base64.b64decode(video_data)
        else:
            video_bytes = bytes(video_data)

        filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
        mime_type = getattr(output_video, "mime_type", "video/mp4") or "video/mp4"

        # (1) Save video with tool_context.save_artifact so it shows up in Playground's Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        save_res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
        import inspect
        if inspect.isawaitable(save_res):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(save_res)
                else:
                    loop.run_until_complete(save_res)
            except Exception:
                pass

        # (2) Upload the same video bytes to the public Cloud Storage bucket and return public URL
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "message": f"Generated video for '{dish_description}'.",
            "video_url": public_url,
            "filename": filename,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload dish video: {str(e)}"}


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


# Configure Agent Engine Sandbox Code Executor for safe Python execution
code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name="projects/1023127694278/locations/us-central1/reasoningEngines/4557771740637298688/sandboxEnvironments/4339310874826113024"
)

# Configure A2UI Schema Manager (version 0.8) and Basic Catalog
if A2uiSchemaManager is not None and BasicCatalog is not None:
    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )
    instruction = schema_manager.generate_system_prompt(
        role_description=(
            "You are ChefPal, an expert AI Personal Chef and culinary assistant. "
            "You strictly remember and track all user allergies, ingredient intolerances, and dietary restrictions across all conversations. "
            "Whenever a user mentions an allergy or dietary restriction, acknowledge it and ensure it is remembered. "
            "Before recommending recipes, ingredients, or meal plans, always check remembered user allergies to ensure food safety. "
            "You help users manage their pantry inventory, suggest recipes based on what ingredients they have, "
            "scale recipe ingredients for different group sizes, look up online recipes, find nearby grocery stores or supermarkets, "
            "generate appetizing food photography for dishes, and run Python calculations or scripts safely in a sandbox. "
            "Always use the available tools or code execution to inspect or update the pantry, search recipes, geocode addresses, find stores, generate dish images, or run computations."
        ),
        workflow_description="Analyze the request, call relevant tools as needed, and return structured UI when appropriate.",
        ui_description=(
            "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
            "Never nest a Card inside a Card. "
            "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
            "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
            "nothing in adk web). "
            "You may include one Image component, but only when you have a public https "
            "URL for the image (for example the URL an image tool returns after uploading "
            "to a public bucket). Set the Image url to that exact https link, for example "
            "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
            "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
            "not have a public URL, add a short Text line noting the image instead. "
            "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
            "headings and emphasis. "
            "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
            "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
        ),
        include_schema=True,
        include_examples=True,
    )
else:
    instruction_path = os.path.join(os.path.dirname(__file__), "a2ui_instruction.txt")
    if os.path.exists(instruction_path):
        with open(instruction_path, "r", encoding="utf-8") as f:
            instruction = f.read()
    else:
        instruction = (
            "You are ChefPal, an expert AI Personal Chef and culinary assistant. "
            "You strictly remember and track all user allergies, ingredient intolerances, and dietary restrictions across all conversations. "
            "Whenever a user mentions an allergy or dietary restriction, acknowledge it and ensure it is remembered. "
            "Before recommending recipes, ingredients, or meal plans, always check remembered user allergies to ensure food safety."
        )

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        list_pantry_items,
        update_pantry_item,
        search_recipes,
        scale_recipe_ingredients,
        fetch_online_recipes,
        geocode_address,
        find_nearby_places,
        generate_dish_image,
        generate_dish_video,
    ],
    code_executor=code_executor,
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
