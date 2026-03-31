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
                return render_template("index.html", result={"error": "Please upload both images."})

            # Save files
            os.makedirs("static/uploads", exist_ok=True)

            front_path = f"static/uploads/front_{front.filename}"
            back_path = f"static/uploads/back_{back.filename}"

            front.save(front_path)
            back.save(back_path)

            # Encode for OpenAI
            front_img = encode_image(open(front_path, "rb"))
            back_img = encode_image(open(back_path, "rb"))

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Analyze this postcard. Return JSON with: overview, analysis, story, timeline."},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                    ]
                }]
            )

            output = response.output[0].content[0].text

            result = {
                "overview": output,
                "analysis": "",
                "story": "",
                "timeline": ""
            }

        except Exception as e:
            result = {"error": str(e)}

    return render_template("index.html", result=result, front_path=front_path, back_path=back_path)

# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)