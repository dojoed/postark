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
        return None

# --- HTML ---
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Postcard Archaeology</title>

<style>
body { margin:0; font-family: Georgia; background:#f5ecd9; }
.wrapper { display:flex; height:100vh; }
.left { width:32%; padding:30px; background:#efe3c2; border-right:2px solid #d6c7a1; }
.right { width:68%; padding:30px; overflow-y:auto; }

.logo { width:160px; margin-bottom:10px; }
.tagline { font-size:14px; margin-bottom:20px; }

.upload-box { background:#fdf6e3; border:2px dashed #cbb88a; padding:20px; border-radius:8px; }

button {
    width:100%;
    padding:12px;
    background:#8b6f47;
    color:white;
    border:none;
    border-radius:6px;
    margin-top:15px;
}

.output-images { display:flex; gap:15px; margin-bottom:20px; }
.output-images img { width:48%; border-radius:6px; }

.tabs { display:flex; gap:10px; margin-bottom:15px; }
.tab { padding:8px 14px; background:#d6c7a1; cursor:pointer; border-radius:6px; }
.tab.active { background:#8b6f47; color:white; }

.tab-content { display:none; }
.tab-content.active { display:block; }

.card { background:#fffaf0; padding:20px; border-radius:8px; }

.story-section { margin-bottom:15px; }
.story-title { font-weight:bold; margin-bottom:5px; }
</style>

<script>
function showTab(id) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    document.getElementById(id+'-tab').classList.add('active');
}
</script>

</head>
<body>

<div class="wrapper">

<div class="left">
<img src="/static/logo.png" class="logo">
<div class="tagline">Preserving history through postcards</div>

<form method="POST" enctype="multipart/form-data">
<div class="upload-box">
<label>Front</label><br>
<input type="file" name="front" required><br><br>
<label>Back</label><br>
<input type="file" name="back" required>
</div>
<button type="submit">Analyze</button>
</form>
</div>

<div class="right">

{% if raw_data %}

<div class="output-images">
<img src="data:image/jpeg;base64,{{ front_image }}">
<img src="data:image/jpeg;base64,{{ back_image }}">
</div>

<div class="tabs">
<div id="overview-tab" class="tab active" onclick="showTab('overview')">Overview</div>
<div id="stamp-tab" class="tab" onclick="showTab('stamp')">Stamp</div>
<div id="story-tab" class="tab" onclick="showTab('story')">Story</div>
</div>

<!-- OVERVIEW -->
<div id="overview" class="tab-content active card">
{% if data %}
<p><b>Sender:</b> {{ data.sender }}</p>
<p><b>Receiver:</b> {{ data.receiver }}</p>
<p><b>From:</b> {{ data.location_sent_from }}</p>
<p><b>To:</b> {{ data.location_sent_to }}</p>
<p><b>Date:</b> {{ data.date }}</p>
<p>{{ data.full_transcription }}</p>
{% else %}
<pre>{{ raw_data }}</pre>
{% endif %}
</div>

<!-- STAMP -->
<div id="stamp" class="tab-content card">
{% if stamp %}
<p><b>Country:</b> {{ stamp.country }}</p>
<p><b>Denomination:</b> {{ stamp.denomination }}</p>
<p><b>Era:</b> {{ stamp.year_or_era }}</p>
<p><b>Description:</b> {{ stamp.description }}</p>
{% else %}
<pre>{{ stamp_raw }}</pre>
{% endif %}

<img src="data:image/png;base64,{{ stamp_image }}" width="160">
</div>

<!-- STORY -->
<div id="story" class="tab-content card">

{% if story %}

<div class="story-section">
<div class="story-title">People & Relationship</div>
<div>{{ story.people }}</div>
</div>

<div class="story-section">
<div class="story-title">Historical Context</div>
<div>{{ story.context }}</div>
</div>

<div class="story-section">
<div class="story-title">Interpretation</div>
<div>{{ story.meaning }}</div>
</div>

<div class="story-section">
<div class="story-title">Confidence</div>
<div>{{ story.confidence }}</div>
</div>

{% else %}
<pre>{{ narrative }}</pre>
{% endif %}

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
                    {"type": "input_text", "text": "Return ONLY JSON with sender, receiver, location_sent_from, location_sent_to, date, full_transcription"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_b64}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_b64}"}
                ]
            }]
        )

        raw_data = vision.output[0].content[0].text
        data = safe_json_parse(raw_data)

        # --- STAMP (STRICT JSON) ---
        stamp_resp = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Return ONLY JSON: country, denomination, year_or_era, description for stamp: {raw_data}"
        )

        stamp_raw = stamp_resp.output[0].content[0].text
        stamp = safe_json_parse(stamp_raw)

        # --- IMAGE ---
        cropped = crop_stamp(back_bytes)
        stamp_image = image_to_base64(cropped)

        # --- STORY (STRUCTURED) ---
        story_resp = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
Return ONLY JSON:
{{
 "people": "...",
 "context": "...",
 "meaning": "...",
 "confidence": "high/medium/low"
}}

Postcard: {raw_data}
"""
        )

        story = safe_json_parse(story_resp.output[0].content[0].text)

        return render_template_string(
            HTML,
            data=data,
            raw_data=raw_data,
            stamp=stamp,
            stamp_raw=stamp_raw,
            stamp_image=stamp_image,
            story=story,
            narrative=story_resp.output[0].content[0].text,
            front_image=front_b64,
            back_image=back_b64
        )

    return render_template_string(HTML)