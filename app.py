from flask import Flask, request, render_template
from openai import OpenAI
import base64
import os
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def encode_image(file):
    return base64.b64encode(file.read()).decode()

@app.route("/", methods=["GET", "POST"])
def index():
    result = None

    if request.method == "POST":
        front = request.files["front"]
        back = request.files["back"]

        front_img = encode_image(front)
        back_img = encode_image(back)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Analyze this postcard and extract key details."},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                ]
            }]
        )

        result = response.output[0].content[0].text

    return render_template("index.html", result=result)

if __name__ == "__main__":
    if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)