from flask import Flask, request, render_template_string
from openai import OpenAI
import os
import base64
import json
from dotenv import load_dotenv
from PIL import Image
import io

# --- SETUP ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

# --- HELPERS ---
def encode_image(file):
    return base64.b64encode(file.read()).decode("utf-8")

def crop_stamp(file):
    image = Image.open(file)
    width, height = image.size

    crop_box = (
        int(width * 0.65),
        0,
        width,
        int(height * 0.35)
    )

    return image.crop(crop_box)

def image_to_base64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- HTML TEMPLATE ---
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Postcard History Agent</title>
    <style>
        body {
            font-family: Arial;
            background: #111;
            color: #eee;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: auto;
        }
        .card {
            background: #1e1e1e;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 10px;
        }
        .row {
            display: flex;
            gap: 20px;
        }
        img {
            max-width: 100%;
            border-radius: 8px;
        }
        .story {
            background: #0f172a;
            padding: 16px;
            border-radius: 10px;
            line-height: 1.6;
        }
    </style>
</head>
<body>
<div class="container">

<h1>📬 Postcard History Agent</h1>

<form method="POST" enctype="multipart/form-data">
    <p>Front Image:</p>
    <input type="file" name="front" required>
    <p>Back Image:</p>
    <input type="file" name="back" required>
    <br><br>
    <button type="submit">Analyze</button>
</form>

{% if data %}

<div class="card">
    <h2>🧾 Postcard Details</h2>
    <pre>{{ data }}</pre>
</div>

<div class="card">
    <h2>📮 Stamp Analysis</h2>

    <div class="row">
        <div style="flex:1;">
            <img src="data:image/png;base64,{{ stamp_image }}">
        </div>

        <div style="flex:2;">
            <h3>Details</h3>
            <pre>{{ stamp_data }}</pre>
        </div>
    </div>
</div>

<div class="card">
    <h2>📖 Historical Narrative</h2>
    <div class="story">
        {{ narrative }}
    </div>
</div>

{% endif %}

</div>
</body>
</html>
"""

# --- ROUTE ---
@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":
        front = request.files["front"]
        back = request.files["back"]

        front_bytes = front.read()
        back_bytes = back.read()

        front_base64 = base64.b64encode(front_bytes).decode()
        back_base64 = base64.b64encode(back_bytes).decode()

        # --- VISION ---
        vision = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extract postcard data as JSON"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_base64}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_base64}"}
                ]
            }]
        )

        data = vision.output[0].content[0].text

        # --- STAMP ANALYSIS ---
        stamp = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Analyze the stamp and return structured details: {data}"
        )

        stamp_data = stamp.output[0].content[0].text

        # --- STAMP IMAGE ---
        back_img = Image.open(io.BytesIO(back_bytes))
        width, height = back_img.size

        crop_box = (
            int(width * 0.65),
            0,
            width,
            int(height * 0.35)
        )

        cropped = back_img.crop(crop_box)
        stamp_image = image_to_base64(cropped)

        # --- NARRATIVE ---
        narrative = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Explain the historical context of this postcard: {data}"
        )

        narrative_text = narrative.output[0].content[0].text

        return render_template_string(
            HTML,
            data=data,
            stamp_data=stamp_data,
            stamp_image=stamp_image,
            narrative=narrative_text
        )

    return render_template_string(HTML, data=None)


if __name__ == "__main__":
    app.run(debug=True)