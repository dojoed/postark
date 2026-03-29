print("SCRIPT STARTED")
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64

# Environment setup
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Research agent

from serpapi import GoogleSearch

def web_search(query):
    print(f"🌐 Real search: {query}")

    params = {
        "engine": "google",
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": 5
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    snippets = []

    if "organic_results" in results:
        for r in results["organic_results"]:
            snippet = r.get("snippet", "")
            title = r.get("title", "")
            snippets.append(f"{title}: {snippet}")

    return "\n".join(snippets)


## Research more
def decide_next_action(structured_data, research_results):
    prompt = f"""
    You are an AI research agent.

    Current postcard data:
    {structured_data}

    Research completed so far:
    {research_results}

    Decide the NEXT BEST action:

    Options:
    - SEARCH: <query>
    - DONE

    Rules:
    - Search for sender, receiver, location, or historical context
    - Avoid repeating the same search
    - Stop when enough context is gathered

    Respond with ONLY one line.
    """

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output[0].content[0].text.strip()

# --- helper: encode image ---
def encode_image(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# --- load images ---
front_image = encode_image("front.jpg")
back_image = encode_image("back.jpg")

print("Images loaded and encoded...")


# --- STEP 1: VISION EXTRACTION ---
vision_prompt = """
You are a historical postcard analyst.

Carefully examine BOTH images of a postcard (front and back).

Extract the following in JSON:

{
  "sender": "",
  "receiver": "",
  "location_sent_from": "",
  "location_sent_to": "",
  "date": "",
  "full_transcription": "",
  "observations": ""
}

Important:
- Read handwriting carefully
- Use best judgment if text is unclear
- Include ALL readable text in transcription
"""

print("Sending images to model...")

response = client.responses.create(
    model="gpt-4.1-mini",
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": vision_prompt},
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{front_image}",
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{back_image}",
                },
            ],
        }
    ],
)

structured = response.output[0].content[0].text


print("\n--- STRUCTURED DATA ---\n")
print(structured)

# Reserach extract
import json

# Convert structured JSON string into dict
data = json.loads(structured)

# --- AGENT RESEARCH LOOP ---
research_results = {}
max_steps = 5

print("\n--- AGENT RESEARCH LOOP ---\n")

for step in range(max_steps):
    action = decide_next_action(structured, research_results)
    print(f"Step {step+1}: {action}")

    if action.startswith("SEARCH:"):
        query = action.replace("SEARCH:", "").strip()

        # prevent duplicate searches
        if query in research_results:
            print("Already searched, skipping...")
            continue

        print(f"Running search for: {query}")
        result = web_search(query)

        research_results[query] = result

    elif action == "DONE":
        print("Research complete.")
        break

## Agent Prompt 2
# --- STEP 2: NARRATIVE ---
narrative_prompt = f"""
You are a historical researcher.

POSTCARD DATA:
{structured}

RESEARCH FINDINGS:
{research_results}

Write a detailed, grounded historical narrative:
- Who these people likely were
- Their relationship
- What was happening historically at that time/place
- What this postcard meant in context

Be realistic:
- Do not invent specific identities unless highly confident
- Use research to support conclusions
"""

print("Generating narrative...")

narrative = client.responses.create(
    model="gpt-4.1",
    input=narrative_prompt
)

print("\n--- NARRATIVE ---\n")
print(narrative.output[0].content[0].text)