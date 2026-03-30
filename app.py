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

    if request.method == "POST":
        try:
            front = request.files.get("front")
            back = request.files.get("back")

            if not front or not back:
                return render_template("index.html", result="Please upload both images.")

            front_img = encode_image(front)
            back_img = encode_image(back)

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Analyze this postcard. Extract sender, receiver, date, location, and summarize the message."},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                    ]
                }]
            )

            result = response.output[0].content[0].text

        except Exception as e:
            result = f"Error: {str(e)}"

    return render_template("index.html", result=result)

# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)