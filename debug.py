import os
from dotenv import load_dotenv
import litellm

# Load your .env file
load_dotenv()

print("Sending request to proxy...")

try:
    response = litellm.completion(
        model=os.getenv("MODEL_NAME", "openai/gemini-2.5-flash"),
        messages=[{"role": "user", "content": "Say 'hello' in one word."}],
        api_key=os.getenv("LITELLM_API_KEY"),
        api_base=os.getenv("LITELLM_BASE_URL"),
    )
    # Print the raw response object so we can see the hidden error/structure
    print("\n--- RAW RESPONSE ---")
    print(response)
    print("--------------------\n")
    
except Exception as e:
    print(f"\nAPI CRASHED WITH ERROR: {e}")