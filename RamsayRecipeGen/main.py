from scraper import search_allrecipes
from chat import ramsay_chat
import time

ingredient_list = []

while True:
    user_input = input("What's the next ingredient? (or type 'done'): ").lower().strip()
    if user_input == "done": 
        break

    ingredient_list.append(user_input)
    print(f"Beautiful! Added {user_input}.")

print("\nLook at that! We're cooking with:", ingredient_list)

Dietary_restrictions = input("What dietary restrictions do you have? (Vegan, Vegetarian, Kosher, halal): ")
Cuisines = ["Dessert", "Italian", "Mexican", "Chinese", "American", "Any"]
print("Here are the Cuisines:", Cuisines)
Cuisine = input("Pick one of the cuisines options: ")

Level_cooking = input("What are you looking to make a simple, medium, or complex: ")
time_limit = int(input("How much time do you have to pepare this meal (type an number): "))
print(f"\nRight! We're making a stunning {Dietary_restrictions} {Cuisine} {Level_cooking}  in just {time_limit}  minutes using {ingredient_list}. Let's get to work!")

print(f"\n[Chef Ramsay]: Checking the local markets for the best ingredients...")
time.sleep(2)

search_query = f"{ingredient_list[0]} {Cuisine}"

print(f"\n[Chef Ramsay]: Searching the pantry for {Cuisine} recipes... Hang tight!")

try:
    results = search_allrecipes(query=search_query, dietary_restrictions=[Dietary_restrictions])
    if not results:
        # If no error but no results, the search might have been too specific
        print("[Chef Ramsay]: My word, that's a rare combination! I'll have to use my own recipe!")
except Exception as e:
    # This will tell us if it's a 403 (Forbidden) or 404 (Not Found)
    print(f"\n[Chef Ramsay]: The kitchen is blocked! (Technical Error: {e})")
    results = []

if results:
    top_recipe = results[0]
    current_recipe = {
        "title": top_recipe.title,
        "ingredients": top_recipe.ingredients,
        "steps": top_recipe.cook_time, # Time is part of that enriched data!
        "url": top_recipe.url,
        "dietary_info": top_recipe.dietary_info  # <--- Use the dietary_info from that block!
    }
    print(f"[Chef Ramsay]: Found it! A stunning {current_recipe['title']}!")

else:
    # --- THIS IS THE EMERGENCY BACKUP ---
    print("[Chef Ramsay]: The validation's a bit slow, but I've got a stunning dish in my head!")
    current_recipe = {
        "title": f"Ramsay's Signature {Cuisine} {ingredient_list[0].capitalize()}",
        "ingredients": ingredient_list,
        "steps": "Sear, season, and plate it like a hero!",
        "url": "Hand-crafted by Gordon"
    }
    print(f"[Chef Ramsay]: We're making my {current_recipe['title']}!")

while True:
    user_q = input("\n[You]: ")
    if user_q.lower() in ["exit", "done"]:
        break
    
    bot_response = ramsay_chat(user_q, current_recipe)
    print(f"\n[Chef Ramsay]: {bot_response}")
