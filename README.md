# Ramsay
A web app that shows recipes based on selected food preferences using Gemini AI and AllRecipes

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
7. run `py backend/main.py`