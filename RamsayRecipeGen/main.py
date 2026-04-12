from scraper import search_allrecipes
from chat import ramsay_chat

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

search_query = f"{' '.join(ingredient_list)} {Cuisine}"

print(f"\n[Chef Ramsay]: Searching the pantry for {Cuisine} recipes... Hang tight!")

results = search_allrecipes(
    query=search_query,
    max_results=3, # Let's get 3 options to choose from
    dietary_restrictions=[Dietary_restrictions] if Dietary_restrictions != "None" else None
)

if not results:
    print("[Chef Ramsay]: DISASTER! I found nothing! We're going to have to wing it with the eggs.")
else:
    top_recipe = results[0]
    current_recipe = {
        "title": top_recipe.title,
        "ingredients": top_recipe.ingredients.split('\n') if top_recipe.ingredients else [],
        "steps": top_recipe.cook_time or "Follow the method on the site!", # or teammate's instructions
        "url": top_recipe.url
    }
    print(f"[Chef Ramsay]: Found it! A stunning {current_recipe['title']}!")

while True:
    user_q = input("\n[You]: ")
    if user_q.lower() in ["exit", "done"]:
        break
    
    bot_response = ramsay_chat(user_q, current_recipe)
    print(f"\n[Chef Ramsay]: {bot_response}")
