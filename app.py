from flask import Flask, request, render_template
from openai import OpenAI
import base64
import os
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- HELPERS ---
def encode_image(file):
    return base64.b64encode(file.read()).decode("utf-8")


def parse_sections(text):
    sections = {
        "overview": "",
        "analysis": "",
        "story": "",
        "timeline": ""
    }

    current_section = None

    for line in text.split("\n"):
        line_lower = line.lower()

        if "overview" in line_lower:
            current_section = "overview"
            continue
        elif "analysis" in line_lower:
            current_section = "analysis"
            continue
        elif "story" in line_lower:
            current_section = "story"
            continue
        elif "timeline" in line_lower:
            current_section = "timeline"
            continue

        if current_section:
            sections[current_section] += line + "\n"

    return sections


# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    if request.method == "POST":
        try:
            front = request.files.get("front")
            back = request.files.get("back")

            if not front or not back:
                return render_template("index.html", result={"error": "Please upload both images."})

            front_img = encode_image(front)
            back_img = encode_image(back)

            prompt = """
You are an expert historical archivist analyzing a vintage postcard.

Return your response in the following labeled sections:

OVERVIEW:
- Short summary of the postcard

ANALYSIS:
- Sender (if visible)
- Receiver (if visible)
- Date (or best estimate)
- Location (origin and/or destination)
- Key visual details
- Message summary

STORY:
- Reconstruct a plausible narrative of the people and context

TIMELINE:
- Bullet points of key inferred events (date-based if possible)

Be specific, thoughtful, and historically aware.
"""

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                    ]
                }]
            )

            raw_text = response.output[0].content[0].text
            parsed = parse_sections(raw_text)

            result = parsed

        except Exception as e:
            result = {"error": str(e)}

    return render_template("index.html", result=result)


# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)