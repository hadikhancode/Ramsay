import os
import requests
from dotenv import load_dotenv
load_dotenv()

chat_history = []

ramsay_persona = """
You are Gordon Ramsay in MasterChef Junior mode. 
- You are high-energy, encouraging, and use British slang like 'spot on' and 'stunning'.
- You NEVER insult the user. Instead, you give constructive advice.
- You know everything about cooking techniques.
- Always refer to the user as 'Chef'.
"""

def ramsay_chat(user_message, recipe):
    API_KEY = os.getenv("FEATHERLESS_API_KEY")
    URL = "https://api.featherless.ai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}", 
        "Content-Type": "application/json"
        }
    
    chat_history.append({"role": "user", "content": user_message})
    
    messages = [
        {"role": "system", "content": ramsay_persona + f"\nContext: You are helping with this recipe: {recipe}"}
    ] + chat_history
    
    payload = {
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "messages": messages,
        "temperature": 0.7
    }

    response = requests.post(URL, headers=headers, json=payload)
    if response.status_code == 200:
        answer = response.json()['choices'][0]['message']['content']
        # Save Ramsay's reply to history 
        chat_history.append({"role": "assistant", "content": answer})
        return answer
    else:
        return "Error connecting to the kitchen!"  

   





