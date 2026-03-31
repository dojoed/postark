from flask import Flask, request, render_template_string
from openai import OpenAI
import os
import base64
import json
from dotenv import load_dotenv
from PIL import Image
import io
import requests

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

def geocode_location(location):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": location, "format": "json"}
        headers = {"User-Agent": "postcard-app"}
        res = requests.get(url, params=params, headers=headers).json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    except:
        pass
    return None, None

# --- HTML TEMPLATE ---
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Postcard Archaeology</title>

<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>

<style>
body { margin:0; font-family: Georgia; background:#f5ecd9; }
.wrapper { display:flex; height:100vh; }

.left { width:32%; padding:30px; background:#efe3c2; border-right:2px solid #d6c7a1; }
.right { width:68%; padding:30px; overflow-y:auto; }

.logo { width:220px; margin-bottom:10px; }

.tagline {
    font-size:15px;
    margin-bottom:25px;
    line-height:1.4;
}

/* MODERN UPLOAD */
.upload-box {
    background:#fdf6e3;
    border-radius:10px;
    padding:20px;
}

.upload-title {
    font-weight:bold;
    margin-bottom:12px;
}

.drop-zone {
    border:2px dashed #cbb88a;
    padding:18px;
    border-radius:8px;
    background:#fffaf0;
    transition:0.2s;
}

.drop-zone:hover {
    border-color:#8b6f47;
    background:#f7efd9;
}

input[type="file"] {
    display:block;
    margin-top:8px;
    margin-bottom:15px;
}

/* BUTTON */
button {
    width:100%;
    padding:12px;
    background:#8b6f47;
    color:white;
    border:none;
    border-radius:6px;
    margin-top:15px;
    font-size:15px;
}

/* OUTPUT */
.output-images {
    display:flex;
    gap:15px;
    margin-bottom:20px;
}

.output-images img {
    width:48%;
    border-radius:6px;
}

/* TABS */
.tabs { display:flex; gap:10px; margin-bottom:15px; }

.tab {
    padding:8px 14px;
    background:#d6c7a1;
    cursor:pointer;
    border-radius:6px;
}

.tab.active {
    background:#8b6f47;
    color:white;
}

.tab-content { display:none; }
.tab-content.active { display:block; }

.card {
    background:#fffaf0;
    padding:20px;
    border-radius:8px;
}

/* STORY */
.story-section { margin-bottom:15px; }

/* MAP */
#map {
    height:400px;
    border-radius:8px;
}
</style>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

<script>
function showTab(id) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    document.getElementById(id).classList.add('active');
    document.getElementById(id+'-tab').classList.add('active');

    if(id === "map") setTimeout(initMap, 100);
}

function initMap() {
    if (!window.mapInitialized) {
        var lat = {{ lat if lat else 0 }};
        var lon = {{ lon if lon else 0 }};

        var map = L.map('map').setView([lat, lon], 5);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        {% if lat and lon %}
        L.marker([lat, lon]).addTo(map)
            .bindPopup("{{ location }}")
            .openPopup();
        {% endif %}

        window.mapInitialized = true;
    }
}
</script>

</head>
<body>

<div class="wrapper">

<!-- LEFT -->
<div class="left">

<img src="/static/logo.png" class="logo">

<div class="tagline">
Preserving history through postcards — uncovering people, places, and forgotten stories.
</div>

<form method="POST" enctype="multipart/form-data">

<div class="upload-box">

<div class="upload-title">Upload Postcard</div>

<div class="drop-zone">
<label>Front Image</label>
<input type="file" name="front" required>

<label>Back Image</label>
<input type="file" name="back" required>
</div>

</div>

<button type="submit">🔍 Analyze Postcard</button>

</form>

</div>

<!-- RIGHT -->
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
<div id="map-tab" class="tab" onclick="showTab('map')">Map</div>
</div>

<!-- OVERVIEW -->
<div id="overview" class="tab-content active card">
<p><b>Sender:</b> {{ data.sender if data else "" }}</p>
<p><b>Receiver:</b> {{ data.receiver if data else "" }}</p>
<p><b>From:</b> {{ location }}</p>
<p>{{ data.full_transcription if data else raw_data }}</p>
</div>

<!-- STAMP -->
<div id="stamp" class="tab-content card">
{% if stamp %}
<p><b>Country:</b> {{ stamp.country }}</p>
<p><b>Denomination:</b> {{ stamp.denomination }}</p>
<p><b>Era:</b> {{ stamp.year_or_era }}</p>
<p><b>Description:</b> {{ stamp.description }}</p>
<p><b>Confidence:</b> {{ stamp.confidence }}</p>
{% else %}
<pre>{{ stamp_raw }}</pre>
{% endif %}
<br>
<img src="data:image/png;base64,{{ stamp_image }}" width="160">
</div>

<!-- STORY -->
<div id="story" class="tab-content card">

{% if story %}
<div class="story-section"><b>People:</b><br>{{ story.people }}</div>
<div class="story-section"><b>Context:</b><br>{{ story.context }}</div>
<div class="story-section"><b>Meaning:</b><br>{{ story.meaning }}</div>
<div class="story-section"><b>Confidence:</b> {{ story.confidence }}</div>
{% else %}
<pre>{{ narrative }}</pre>
{% endif %}

</div>

<!-- MAP -->
<div id="map" class="tab-content card">
<div id="map"></div>
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
                    {"type": "input_text", "text": "Return JSON: sender, receiver, location_sent_from, full_transcription"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_b64}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_b64}"}
                ]
            }]
        )

        raw_data = vision.output[0].content[0].text
        data = safe_json_parse(raw_data)

        location = data.get("location_sent_from") if data else None
        lat, lon = geocode_location(location) if location else (None, None)

        # --- STAMP (FIXED) ---
        stamp_resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Analyze ONLY the stamp and return JSON: country, denomination, year_or_era, description, confidence"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_b64}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_b64}"}
                ]
            }]
        )

        stamp_raw = stamp_resp.output[0].content[0].text
        stamp = safe_json_parse(stamp_raw)

        # --- STORY ---
        story_resp = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
Return JSON:
people, context, meaning, confidence

Postcard: {raw_data}
"""
        )

        story = safe_json_parse(story_resp.output[0].content[0].text)

        # --- IMAGE ---
        cropped = crop_stamp(back_bytes)
        stamp_image = image_to_base64(cropped)

        return render_template_string(
            HTML,
            data=data,
            raw_data=raw_data,
            stamp=stamp,
            stamp_raw=stamp_raw,
            story=story,
            narrative=story_resp.output[0].content[0].text,
            stamp_image=stamp_image,
            front_image=front_b64,
            back_image=back_b64,
            location=location,
            lat=lat,
            lon=lon
        )

    return render_template_string(HTML)