from flask import Flask, request, render_template_string
from openai import OpenAI
import os, base64, json, io, requests
from dotenv import load_dotenv
from PIL import Image

# --- SETUP ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
DATA_FILE = "postcards.json"

# --- STORAGE ---
def load_postcards():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_postcard(entry):
    data = load_postcards()
    data.append(entry)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- HELPERS ---
def encode_bytes(b): return base64.b64encode(b).decode()

def crop_stamp(b):
    img = Image.open(io.BytesIO(b))
    w,h = img.size
    return img.crop((int(w*0.65),0,w,int(h*0.35)))

def image_to_base64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def safe_json(t):
    try:
        return json.loads(t.replace("```json","").replace("```","").strip())
    except:
        return {}

def geocode(loc):
    try:
        r=requests.get("https://nominatim.openstreetmap.org/search",
        params={"q":loc,"format":"json"},
        headers={"User-Agent":"app"}).json()
        if r: return float(r[0]["lat"]),float(r[0]["lon"])
    except: pass
    return None,None

# --- HTML ---
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Postcard Archaeology</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>

<style>
body{margin:0;font-family:Georgia;background:#f5ecd9;}
.wrapper{display:flex;height:100vh;}

.left{width:32%;padding:30px;background:#efe3c2;border-right:2px solid #d6c7a1;}
.right{width:68%;padding:30px;overflow-y:auto;}

.logo{width:100%;margin-bottom:15px;}
.tagline{font-size:14px;margin-bottom:25px;color:#5a4d36;}

/* 🔥 MODERN UPLOAD */
.upload-zone{
    border:2px dashed #cbb88a;
    border-radius:12px;
    padding:25px;
    text-align:center;
    background:#fffaf0;
    cursor:pointer;
    transition:0.2s;
    margin-bottom:15px;
}
.upload-zone:hover{
    background:#f7efd9;
    border-color:#8b6f47;
}

.upload-zone input{
    display:none;
}

.upload-text{
    font-size:14px;
    color:#6b5e45;
}

.preview{
    margin-top:10px;
}

.preview img{
    width:100%;
    border-radius:6px;
}

/* BUTTON */
button{
    width:100%;
    padding:12px;
    background:#8b6f47;
    color:white;
    border:none;
    border-radius:6px;
    margin-top:10px;
}

/* OUTPUT */
.output-images{display:flex;gap:15px;margin-bottom:20px;}
.output-images img{width:48%;border-radius:6px;}

.tabs{display:flex;gap:10px;margin-bottom:15px;}
.tab{padding:8px 14px;background:#d6c7a1;cursor:pointer;border-radius:6px;}
.tab.active{background:#8b6f47;color:white;}

.tab-content{display:none;}
.tab-content.active{display:block;}

.card{background:#fffaf0;padding:20px;border-radius:8px;}
#map{height:400px;border-radius:8px;}
</style>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

<script>
function previewFile(input, id){
    const file = input.files[0];
    if(file){
        const reader = new FileReader();
        reader.onload = function(e){
            document.getElementById(id).innerHTML =
                "<img src='"+e.target.result+"'>";
        };
        reader.readAsDataURL(file);
    }
}

function showTab(id){
 document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
 document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
 document.getElementById(id).classList.add('active');
 document.getElementById(id+'-tab').classList.add('active');
 if(id==='map'){setTimeout(initMap,100);}
}

function initMap(){
 if(window.mapLoaded)return;
 var map=L.map('map').setView([20,0],2);
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

 var data={{postcards|tojson}};
 data.forEach(p=>{
  if(p.lat && p.lon){
   L.marker([p.lat,p.lon]).addTo(map)
   .bindPopup("<b>"+p.location+"</b><br><img src='data:image/jpeg;base64,"+p.front+"' width='120'>");
  }
 });

 window.mapLoaded=true;
}
</script>

</head>
<body>

<div class="wrapper">

<div class="left">
<img src="/static/logo.png" class="logo">
<div class="tagline">Preserving history through postcards.</div>

<form method="POST" enctype="multipart/form-data">

<label class="upload-zone">
<div class="upload-text">Click or drag front image</div>
<input type="file" name="front" onchange="previewFile(this,'p1')" required>
<div id="p1" class="preview"></div>
</label>

<label class="upload-zone">
<div class="upload-text">Click or drag back image</div>
<input type="file" name="back" onchange="previewFile(this,'p2')" required>
<div id="p2" class="preview"></div>
</label>

<button>Analyze</button>
</form>
</div>

<div class="right">

{% if raw %}

<div class="output-images">
<img src="data:image/jpeg;base64,{{front}}">
<img src="data:image/jpeg;base64,{{back}}">
</div>

<div class="tabs">
<div id="overview-tab" class="tab active" onclick="showTab('overview')">Overview</div>
<div id="stamp-tab" class="tab" onclick="showTab('stamp')">Stamp</div>
<div id="story-tab" class="tab" onclick="showTab('story')">Story</div>
<div id="map-tab" class="tab" onclick="showTab('map')">Map</div>
</div>

<div id="overview" class="tab-content active card">
<p>{{data.full_transcription}}</p>
</div>

<div id="stamp" class="tab-content card">
<p>{{stamp.description}}</p>
<img src="data:image/png;base64,{{stamp_img}}" width="160">
</div>

<div id="story" class="tab-content card">
<p>{{story.meaning}}</p>
</div>

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
@app.route("/", methods=["GET","POST"])
def index():

    posts=load_postcards()

    if request.method=="POST":
        f=request.files["front"].read()
        b=request.files["back"].read()

        f64=encode_bytes(f)
        b64=encode_bytes(b)

        v=client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role":"user","content":[
                {"type":"input_text","text":"Return JSON: location_sent_from,full_transcription"},
                {"type":"input_image","image_url":f"data:image/jpeg;base64,{f64}"},
                {"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"}
            ]}]
        )

        raw=v.output[0].content[0].text
        data=safe_json(raw)

        loc=data.get("location_sent_from")
        lat,lon=geocode(loc)

        s=client.responses.create(
            model="gpt-4.1-mini",
            input="Describe the stamp"
        )

        stamp={"description":s.output[0].content[0].text}

        st=client.responses.create(
            model="gpt-4.1-mini",
            input=f"Explain this postcard: {raw}"
        )

        story={"meaning":st.output[0].content[0].text}

        save_postcard({"location":loc,"lat":lat,"lon":lon,"front":f64})

        return render_template_string(
            HTML,
            raw=raw,
            data=data,
            stamp=stamp,
            story=story,
            front=f64,
            back=b64,
            stamp_img=image_to_base64(crop_stamp(b)),
            postcards=load_postcards()
        )

    return render_template_string(HTML,postcards=posts)