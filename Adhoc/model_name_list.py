import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")


client = genai.Client(api_key=api_key)

print("List of models that support generateContent:\n")
for m in client.models.list():
    for action in m.supported_actions:
        if action == "generateContent":
            print(m.name)


if __name__ ==  "__main__":
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents = ['What is your name?'])

    print(response.model_version)