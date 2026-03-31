from flask import Flask, request, render_template
from openai import OpenAI
import base64
import os
import json
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- HELPERS ---
def encode_image(file):
    return base64.b64encode(file.read()).decode("utf-8")

def save_file(file, filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.seek(0)
    file.save(path)
    return path

def safe_parse_response(text):
    try:
        data = json.loads(text)
        return {
            "overview": data.get("overview", ""),
            "analysis": data.get("analysis", ""),
            "story": data.get("story", ""),
            "timeline": data.get("timeline", "")
        }
    except:
        return {
            "overview": text,
            "analysis": "",
            "story": "",
            "timeline": ""
        }

# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    front_path = None
    back_path = None

    if request.method == "POST":
        try:
            front = request.files.get("front")
            back = request.files.get("back")

            if not front or not back:
                return render_template("index.html", result={"error": "Upload both images."})

            front_path = save_file(front, "front.jpg")
            back_path = save_file(back, "back.jpg")

            front_img = encode_image(front)
            back_img = encode_image(back)

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": """
Return ONLY valid JSON with keys:
overview, analysis, story, timeline.
"""
                        },
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                    ]
                }]
            )

            try:
                text_output = response.output[0].content[0].text
            except Exception:
                text_output = str(response)

            result = safe_parse_response(text_output)

        except Exception as e:
            result = {"error": str(e)}

    return render_template(
        "index.html",
        result=result,
        front_path=front_path,
        back_path=back_path
    )

# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)