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

# --- HTML ---
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Postcard Archaeology</title>

<style>
body {
    margin: 0;
    font-family: Georgia, serif;
    background: #f5ecd9;
    color: #2c2c2c;
}

.wrapper {
    display: flex;
    height: 100vh;
}

/* LEFT PANEL */
.left {
    width: 35%;
    padding: 40px 30px;
    background: #efe3c2;
    border-right: 2px solid #d6c7a1;
}

/* RIGHT PANEL */
.right {
    width: 65%;
    padding: 40px;
    overflow-y: auto;
}

/* HEADER */
.header {
    margin-bottom: 25px;
}

.logo-img {
    width: 140px;
    margin-bottom: 10px;
}

.title {
    font-size: 26px;
    font-weight: bold;
}

.tagline {
    font-size: 14px;
    color: #6b5e45;
}

/* UPLOAD CARD */
.upload-box {
    border: 2px dashed #cbb88a;
    padding: 25px;
    border-radius: 8px;
    background: #fdf6e3;
    margin-top: 25px;
}

/* INPUT */
input[type="file"] {
    margin-top: 10px;
    margin-bottom: 20px;
}

/* BUTTON */
button {
    width: 100%;
    padding: 12px;
    background: #8b6f47;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 15px;
    cursor: pointer;
}

/* CARDS */
.card {
    background: #fffaf0;
    padding: 24px;
    margin-bottom: 25px;
    border: 1px solid #d6c7a1;
    border-radius: 8px;
}

/* STAMP LAYOUT */
.row {
    display: flex;
    gap: 25px;
    align-items: flex-start;
}

.left-col { flex: 1; }
.right-col { flex: 2; }

/* STORY */
.story {
    background: #fdf6e3;
    padding: 18px;
    border-left: 5px solid #8b6f47;
    line-height: 1.7;
}

/* IMAGES */
img {
    border-radius: 6px;
}
</style>

</head>
<body>

<div class="wrapper">

<!-- LEFT -->
<div class="left">

<div class="header">
    <img src="/static/logo.png" class="logo-img">
    <div class="title">Postcard Archaeology</div>
    <div class="tagline">
        Preserving history through postcards — uncovering people, places, and forgotten stories.
    </div>
</div>

<form method="POST" enctype="multipart/form-data">

<div class="upload-box">
    <label><b>Front Image</b></label><br>
    <input type="file" name="front" required>

    <label><b>Back Image</b></label><br>
    <input type="file" name="back" required>
</div>

<br>
<button type="submit">🔍 Analyze Postcard</button>

</form>

{% if front_image %}
<div class="card">
<h3>Front</h3>
<img src="data:image/jpeg;base64,{{ front_image }}" width="100%">
</div>
{% endif %}

{% if back_image %}
<div class="card">
<h3>Back</h3>
<img src="data:image/jpeg;base64,{{ back_image }}" width="100%">
</div>
{% endif %}

</div>

<!-- RIGHT -->
<div class="right">

{% if data %}

<div class="card">
<h2>🧾 Overview</h2>

<p><b>Sender:</b> {{ data.sender }}</p>
<p><b>Receiver:</b> {{ data.receiver }}</p>
<p><b>From:</b> {{ data.location_sent_from }}</p>
<p><b>To:</b> {{ data.location_sent_to }}</p>
<p><b>Date:</b> {{ data.date }}</p>

<h3>✉️ Message</h3>
<p>{{ data.full_transcription }}</p>
</div>

<div class="card">
<h2>📮 Stamp Analysis</h2>

<div class="row">

<div class="left-col">
<img src="data:image/png;base64,{{ stamp_image }}" width="180">
</div>

<div class="right-col">
<p><b>Country:</b> {{ stamp.country }}</p>
<p><b>Denomination:</b> {{ stamp.denomination }}</p>
<p><b>Era:</b> {{ stamp.year_or_era }}</p>
<p><b>Description:</b> {{ stamp.stamp_description }}</p>

{% if stamp.postmark_details %}
<p><b>Postmark:</b> {{ stamp.postmark_details }}</p>
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

        return render_template_string(
            HTML,
            data=data,
            stamp=stamp_data,
            stamp_image=stamp_image,
            narrative=narrative.output[0].content[0].text,
            front_image=front_b64,
            back_image=back_b64
        )

    return render_template_string(HTML, data=None)