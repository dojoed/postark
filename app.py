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
    crop_box = (int(width * 0.65), 0, width, int(height * 0.35))
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
        return {}

# --- HTML TEMPLATE ---
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
    width: 32%;
    padding: 30px;
    background: #efe3c2;
    border-right: 2px solid #d6c7a1;
}

/* RIGHT PANEL */
.right {
    width: 68%;
    padding: 30px;
    overflow-y: auto;
}

/* HEADER (LOCKED) */
.header {
    margin-bottom: 25px;
}

.logo {
    width: 160px;
    margin-bottom: 10px;
}

.title {
    font-size: 26px;
    font-weight: bold;
}

.tagline {
    font-size: 14px;
    color: #6b5e45;
    margin-bottom: 20px;
}

/* UPLOAD */
.upload-box {
    background: #fdf6e3;
    border: 2px dashed #cbb88a;
    padding: 20px;
    border-radius: 8px;
}

/* BUTTON */
button {
    width: 100%;
    padding: 12px;
    background: #8b6f47;
    color: white;
    border: none;
    border-radius: 6px;
    margin-top: 15px;
    font-size: 15px;
}

/* IMAGE PREVIEW */
.preview img {
    width: 100%;
    margin-top: 12px;
    border-radius: 6px;
}

/* OUTPUT IMAGES */
.output-images {
    display: flex;
    gap: 15px;
    margin-bottom: 20px;
}

.output-images img {
    width: 48%;
    border-radius: 6px;
}

/* TABS */
.tabs {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;
}

.tab {
    padding: 8px 14px;
    background: #d6c7a1;
    cursor: pointer;
    border-radius: 6px;
}

.tab.active {
    background: #8b6f47;
    color: white;
}

/* CONTENT */
.tab-content {
    display: none;
}

.tab-content.active {
    display: block;
}

/* CARD */
.card {
    background: #fffaf0;
    padding: 20px;
    border-radius: 8px;
}

/* STORY */
.story {
    background: #fdf6e3;
    padding: 15px;
    border-left: 4px solid #8b6f47;
    line-height: 1.6;
}
</style>

<script>
function showTab(id) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    document.getElementById(id).classList.add('active');
    document.getElementById(id + '-tab').classList.add('active');
}
</script>

</head>
<body>

<div class="wrapper">

<!-- LEFT PANEL -->
<div class="left">

<div class="header">
    <img src="/static/logo.png" class="logo">
    <div class="title">Postcard Archaeology</div>
    <div class="tagline">
        Preserving history through postcards — uncovering people, places, and forgotten stories.
    </div>
</div>

<form method="POST" enctype="multipart/form-data">

<div class="upload-box">
    <label><b>Front Image</b></label><br>
    <input type="file" name="front" required><br><br>

    <label><b>Back Image</b></label><br>
    <input type="file" name="back" required>
</div>

<button type="submit">🔍 Analyze Postcard</button>

</form>

{% if front_image %}
<div class="preview">
<img src="data:image/jpeg;base64,{{ front_image }}">
<img src="data:image/jpeg;base64,{{ back_image }}">
</div>
{% endif %}

</div>

<!-- RIGHT PANEL -->
<div class="right">

{% if data %}

<!-- IMAGES -->
<div class="output-images">
<img src="data:image/jpeg;base64,{{ front_image }}">
<img src="data:image/jpeg;base64,{{ back_image }}">
</div>

<!-- TABS -->
<div class="tabs">
<div id="overview-tab" class="tab active" onclick="showTab('overview')">Overview</div>
<div id="stamp-tab" class="tab" onclick="showTab('stamp')">Stamp</div>
<div id="story-tab" class="tab" onclick="showTab('story')">Story</div>
</div>

<!-- OVERVIEW -->
<div id="overview" class="tab-content active card">
<p><b>Sender:</b> {{ data.sender }}</p>
<p><b>Receiver:</b> {{ data.receiver }}</p>
<p><b>From:</b> {{ data.location_sent_from }}</p>
<p><b>To:</b> {{ data.location_sent_to }}</p>
<p><b>Date:</b> {{ data.date }}</p>

<h3>Message</h3>
<p>{{ data.full_transcription }}</p>
</div>

<!-- STAMP -->
<div id="stamp" class="tab-content card">
<div style="display:flex; gap:20px;">
<img src="data:image/png;base64,{{ stamp_image }}" width="160">
<div>
<p><b>Country:</b> {{ stamp.country }}</p>
<p><b>Denomination:</b> {{ stamp.denomination }}</p>
<p><b>Era:</b> {{ stamp.year_or_era }}</p>
<p><b>Description:</b> {{ stamp.stamp_description }}</p>
</div>
</div>
</div>

<!-- STORY -->
<div id="story" class="tab-content card">
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
            input=f"Analyze stamp: {data}"
        )

        stamp_data = safe_json_parse(stamp.output[0].content[0].text)

        # --- IMAGE ---
        cropped = crop_stamp(back_bytes)
        stamp_image = image_to_base64(cropped)

        # --- STORY ---
        narrative = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Explain this postcard: {data}"
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