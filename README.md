# Ramsay
A web app that shows recipes based on selected food preferences using Gemini AI and AllRecipes

---

### Features
- Customize food preferences
    - Ingredients
    - Dietary Restrictions
    - Cuisine
    - Event
    - Food Type
    - Exclude Ingredients
    - Allergies/Restrictions
    - Recipe Complexity
    - Recipe Result Amount
- Gemini AI checks all recipes to ensure that the recipe matches the selected preferences
- Featherless AI Chat Bot to ask questions about a recipe to

![Preference options](https://i.luckyc.dev/ramsay1.png)
![Preference options 2 and results amount](https://i.luckyc.dev/ramsay2.png)
![Results example](https://i.luckyc.dev/ramsay3.png)
![Chatbot example](https://i.luckyc.dev/ramsay4.png)

---

### Instructions to run:
1. Create a [Google Cloud Console project](https://console.cloud.google.com/)
    - Go to APIs & Services > Enabled APIS & Services
        - Click Enable APIs & Services button at the top
            - Search for Vertex AI API and enable it
2. Get your [Featherless AI API key](https://featherless.ai/account/api-keys) for the chatbot
3. Install [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install-sdk#latest-version) and log in with your Google account that has access to the project from step 1
4.  run `pip install -r requirements.txt`
5. run `gcloud auth application-default login` and log in with your Google account that has access to the project from step 1 again (this time there will be checkboxes you have to click)
6.  rename .env.example to .env and edit the values (mainly the GOOGLE_CLOUD_CONSOLE_PROJECT_ID and FEATHERLESS_API_KEY values)
7. run `python backend/main.py`

---

- **Note: this may be not be possible to run on a server due to AllRecipes' Cloudflare anti-bot measures and there being no free public AllRecipes API**