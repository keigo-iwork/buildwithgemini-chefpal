# ChefPal - Personal AI Chef & Culinary Concierge

![ChefPal Demo](demo.gif)

> 🎬 **Watch Demo Video with Lo-Fi Music**: [chefpal_demo_lofi.mp4](chefpal_demo_lofi.mp4) | [Original silent demo](chefpal_demo.mp4)

**ChefPal** is an autonomous AI culinary assistant built on Google's Agent Development Kit (ADK) and Agent Engine. It helps home cooks manage pantry stock, recall dietary restrictions and food allergies across sessions, scale recipes with code execution, discover real-world dishes, and generate photorealistic plating presentations and culinary preview videos.

---

## What the Agent Actually Does

All features below are fully implemented and wired in [`app/agent.py`](app/agent.py):

### 1. Cross-Session Allergy & Preference Memory (Vertex AI Memory Bank)
- Automatically remembers user allergies, dietary restrictions, and ingredient intolerances across sessions using `PreloadMemoryTool` and an `after_agent_callback` (`add_session_to_memory`).
- Cross-references remembered allergies before suggesting recipes or meal plans to maintain food safety.

### 2. Live Pantry Inventory Tracking (Google Cloud Firestore)
- Backed by Google Cloud Firestore database (`pantry_items` collection).
- **`list_pantry_items`**: Retrieves available pantry items including ingredient name, quantity, unit, and food category.
- **`update_pantry_item`**: Adds or updates ingredients with quantity and unit.

### 3. Curated Recipes & Serving Scaling (Firestore + Python Code Sandbox)
- **`search_recipes`**: Searches curated recipe documents in Firestore (`recipes` collection) filtering by dietary restrictions or keywords.
- **`scale_recipe_ingredients`**: Computes ingredient ratios and scaling notes for target serving sizes.
- **`AgentEngineSandboxCodeExecutor`**: Leverages an isolated Python code execution sandbox for accurate numerical calculations.

### 4. Live Recipe Search & Grocery Location Tools
- **`fetch_online_recipes`**: Queries TheMealDB API in real time for international dish instructions and ingredients.
- **`geocode_address` & `find_nearby_places`**: Uses Google Maps Geocoding API and Google Places API to find nearby supermarkets and grocery stores based on coordinates.

### 5. Multimodal Image & Video Generation (Cloud Storage & Vertex AI)
- **`generate_dish_image`**: Calls `gemini-3.1-flash-lite-image` via the Vertex AI global endpoint to create food photography. Saves the image as an ADK session artifact and uploads it to Google Cloud Storage (`gs://<bucket>`), returning a public HTTPS URL.
- **`generate_dish_video`**: Calls Google's Omni multimodal model (`gemini-omni-flash-preview`) via the Vertex AI Interactions API in the global region to create short culinary videos. Saves the video as an ADK session artifact and uploads it to Cloud Storage, returning a public HTTPS URL.

### 6. A2UI Rich Card Rendering & Custom Frontend
- Formatted with A2UI schema specifications (`A2uiSchemaManager` v0.8 Basic Catalog).
- Emits structured A2UI cards, columns, rows, text, and images via an `after_model_callback`.
- Delivered through a lightweight FastAPI proxy talking A2A protocol and a custom warm culinary-themed chat UI in `frontend/`.

---

## Project Structure

```
.
├── app/
│   ├── agent.py               # Root ADK agent, tools, callbacks, and configuration
│   ├── a2ui_utils.py          # A2UI event converter for after_model_callback
│   └── a2ui_instruction.txt   # Fallback A2UI system instructions
├── frontend/
│   ├── main.py                # FastAPI proxy communicating over A2A protocol
│   ├── Dockerfile             # Container definition for Cloud Run
│   └── static/
│       └── index.html         # Custom branded chat UI with A2UI renderer and example chips
├── demo.gif                   # Looping walkthrough recording
├── agents-cli-manifest.yaml   # Agent Engine deployment manifest
├── pyproject.toml             # Python dependencies and build metadata
└── README.md
```

---

## Setup & Running Locally

### Prerequisites
- Python 3.11+
- `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Google Cloud CLI (`gcloud`) authenticated with your project:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  gcloud config set project <YOUR_PROJECT_ID>
  ```

### 1. Running the Agent Backend

Install dependencies and start the ADK interactive playground:
```bash
# Sync dependencies
uv sync

# Launch the ADK web playground
uv run adk web app
```

### 2. Running the Custom Frontend

The frontend connects to either the local ADK runner or a deployed Agent Engine resource over A2A:

```bash
cd frontend

# Install frontend dependencies into its environment
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Configure your agent environment variables
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_NUMBER>/locations/<REGION>/reasoningEngines/<REASONING_ENGINE_ID>"
export AGENT_DIRECTORY="app"
export PORT="8080"

# Start the FastAPI server
python main.py
```

---

## Cloud Deployment

### Deploy Agent Engine
```bash
uv run agents-cli deploy \
  --project <YOUR_PROJECT_ID> \
  --region us-central1 \
  --update-env-vars GOOGLE_MAPS_API_KEY=<YOUR_KEY>
```

### Deploy Frontend to Cloud Run
```bash
cd frontend
gcloud run deploy chefpal-frontend \
  --source . \
  --project <YOUR_PROJECT_ID> \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<DEPLOYED_AGENT_RESOURCE_NAME>",AGENT_DIRECTORY="app"
```
