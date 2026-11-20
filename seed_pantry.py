# Copyright 2026 Google LLC
# Seed script for ChefPal Firestore backend

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-91797115bb4a"

INITIAL_PANTRY = [
    {
        "id": "eggs",
        "name": "Eggs",
        "quantity": 12,
        "unit": "pieces",
        "category": "dairy & poultry",
        "notes": "Large brown free-range eggs",
    },
    {
        "id": "milk",
        "name": "Whole Milk",
        "quantity": 1,
        "unit": "liter",
        "category": "dairy",
        "notes": "Fresh whole milk",
    },
    {
        "id": "pasta_spaghetti",
        "name": "Spaghetti Pasta",
        "quantity": 500,
        "unit": "grams",
        "category": "grains & dry goods",
        "notes": "Durum wheat semolina",
    },
    {
        "id": "olive_oil",
        "name": "Extra Virgin Olive Oil",
        "quantity": 750,
        "unit": "ml",
        "category": "oils & condiments",
        "notes": "Cold-pressed",
    },
    {
        "id": "garlic",
        "name": "Garlic",
        "quantity": 3,
        "unit": "heads",
        "category": "produce",
        "notes": "Organic garlic cloves",
    },
    {
        "id": "parmesan_cheese",
        "name": "Parmigiano-Reggiano",
        "quantity": 200,
        "unit": "grams",
        "category": "dairy",
        "notes": "Aged 24 months",
    },
    {
        "id": "black_pepper",
        "name": "Whole Black Peppercorns",
        "quantity": 100,
        "unit": "grams",
        "category": "spices",
        "notes": "For grinder",
    },
]

INITIAL_RECIPES = [
    {
        "id": "classic_carbonara",
        "title": "Classic Spaghetti Carbonara",
        "cuisine": "Italian",
        "prep_time_minutes": 10,
        "cook_time_minutes": 15,
        "servings": 2,
        "ingredients": [
            "200g Spaghetti Pasta",
            "2 Large Eggs + 1 yolk",
            "50g Parmigiano-Reggiano",
            "Fresh cracked Black Pepper",
            "1 tbsp Olive Oil",
        ],
        "instructions": (
            "1. Boil pasta in salted water until al dente.\n"
            "2. Whisk eggs, grated parmesan, and black pepper in a bowl.\n"
            "3. Toss hot drained pasta with egg mixture off heat until creamy.\n"
            "4. Serve immediately with extra grated cheese and cracked black pepper."
        ),
    },
    {
        "id": "garlic_olive_oil_pasta",
        "title": "Spaghetti Aglio e Olio",
        "cuisine": "Italian",
        "prep_time_minutes": 5,
        "cook_time_minutes": 12,
        "servings": 2,
        "ingredients": [
            "200g Spaghetti Pasta",
            "4 cloves Garlic (sliced)",
            "3 tbsp Extra Virgin Olive Oil",
            "Chili flakes or Black Pepper",
        ],
        "instructions": (
            "1. Cook spaghetti in boiling water.\n"
            "2. Gently sauté sliced garlic in olive oil until fragrant and golden.\n"
            "3. Mix pasta directly into the garlic oil with a splash of pasta water.\n"
            "4. Season and serve hot."
        ),
    },
]


def seed():
    print(f"Connecting to Firestore with hardcoded project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)

    pantry_col = db.collection("pantry_items")
    print(f"Seeding {len(INITIAL_PANTRY)} pantry items into 'pantry_items'...")
    for item in INITIAL_PANTRY:
        doc_id = item["id"]
        pantry_col.document(doc_id).set(item)
        print(f"  + Added pantry item: {item['name']} ({item['quantity']} {item['unit']})")

    recipe_col = db.collection("recipes")
    print(f"Seeding {len(INITIAL_RECIPES)} recipes into 'recipes'...")
    for r in INITIAL_RECIPES:
        doc_id = r["id"]
        recipe_col.document(doc_id).set(r)
        print(f"  + Added recipe: {r['title']}")

    print("✅ Firestore seed complete!")


if __name__ == "__main__":
    seed()
