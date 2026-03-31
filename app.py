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
def encode_bytes(file_bytes):
    return base64.b64encode(file_bytes).decode()

def crop_stamp(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
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

def safe_json_parse(text):
    try:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except:
        return {"raw": text}

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
            align-items: flex-start;
        }

        .left {
            flex: 1;
        }

        .right {
            flex: 2;
        }

        .label {
            color: #aaa;
            font-size: 13px;
        }

        .value {
            font-size: 16px;
            margin-bottom: 10px;
        }

        .story {
            background: #0f172a;
            padding: 16px;
            border-radius: 10px;
            line-height: 1.6;
        }

        img {
            border-radius: 8px;
        }

        button {
            padding: 10px 16px;
            border-radius: 6px;
            border: none;
            background: #2563eb;
            color: white;
            font-weight: bold;
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
    <h2>🧾 Overview</h2>

    <div class="value"><span class="label">Sender:</span> {{ data.sender }}</div>
    <div class="value"><span class="label">Receiver:</span> {{ data.receiver }}</div>
    <div class="value"><span class="label">From:</span> {{ data.location_sent_from }}</div>
    <div class="value"><span class="label">To:</span> {{ data.location_sent_to }}</div>
    <div class="value"><span class="label">Date:</span> {{ data.date }}</div>

    <h3>✉️ Message</h3>
    <p>{{ data.full_transcription }}</p>
</div>

<div class="card">
    <h2>📮 Stamp Analysis</h2>

    <div class="row">
        <div class="left">
            <img src="data:image/png;base64,{{ stamp_image }}" width="180">
        </div>

        <div class="right">
            <div class="value"><span class="label">Country:</span> {{ stamp.country }}</div>
            <div class="value"><span class="label">Denomination:</span> {{ stamp.denomination }}</div>
            <div class="value"><span class="label">Era:</span> {{ stamp.year_or_era }}</div>
            <div class="value"><span class="label">Description:</span> {{ stamp.stamp_description }}</div>

            {% if stamp.postmark_details %}
            <div class="value"><span class="label">Postmark:</span> {{ stamp.postmark_details }}</div>
            {% endif %}
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

        front_b64 = encode_bytes(front_bytes)
        back_b64 = encode_bytes(back_bytes)

        # --- VISION ---
        vision = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extract postcard data as JSON"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_b64}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_b64}"}
                ]
            }]
        )

        data = safe_json_parse(vision.output[0].content[0].text)

        # --- STAMP ---
        stamp = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Analyze the stamp and return structured JSON: {data}"
        )

        stamp_data = safe_json_parse(stamp.output[0].content[0].text)

        # --- IMAGE ---
        cropped = crop_stamp(back_bytes)
        stamp_image = image_to_base64(cropped)

        # --- NARRATIVE ---
        narrative = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Explain this postcard with historical context: {data}"
        )

        narrative_text = narrative.output[0].content[0].text

        return render_template_string(
            HTML,
            data=data,
            stamp=stamp_data,
            stamp_image=stamp_image,
            narrative=narrative_text
        )

    return render_template_string(HTML, data=None)