from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import os, base64, json, requests
from dotenv import load_dotenv

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
    new_hash = entry.get("hash")

    for existing in data:
        if existing.get("hash") == new_hash:
            return  # skip duplicate

    data.append(entry)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def delete_postcard_by_hash(hash_value):
    data = load_postcards()
    data = [p for p in data if p.get("hash") != hash_value]

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --- HELPERS ---
def encode_bytes(b): return base64.b64encode(b).decode()

import hashlib

def image_hash(b):
    return hashlib.md5(b).hexdigest()

def safe_json(t):
    try:
        return json.loads(t.replace("```json","").replace("```","").strip())
    except:
        return {}

def clean_field(val):
    return val if val else "Unable to interpret"

def geocode(loc):
    try:
        r=requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q":loc,"format":"json"},
            headers={"User-Agent":"app"}
        ).json()
        if r:
            return float(r[0]["lat"]),float(r[0]["lon"])
    except:
        pass
    return None,None

# --- HTML (UNCHANGED) ---
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Postcard Archaeology</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>

<style>
body{margin:0;font-family:Georgia;background:#f5ecd9;}
.wrapper{display:flex;height:100vh;}
.left{width:26%;padding:30px;background:#efe3c2;}
.right{width:74%;padding:30px;overflow-y:auto;}

.logo{width:100%;margin-bottom:10px;}
.tagline{font-size:14px;color:#5a4d36;margin-bottom:20px;}

.upload-bar{display:flex;gap:20px;margin-bottom:25px;}

.upload-card{
 flex:1;background:#fffaf0;border:2px dashed #cbb892;border-radius:12px;
 padding:20px;text-align:center;position:relative;cursor:pointer;
}

.upload-title{font-weight:bold;margin-bottom:10px;}
.upload-sub{font-size:12px;color:#7a6a4f;margin-bottom:10px;}

.upload-card input{
 position:absolute;width:100%;height:100%;top:0;left:0;opacity:0;cursor:pointer;
}

.preview img{
 width:100%;height:160px;object-fit:contain;background:#f5ecd9;
 border-radius:6px;margin-top:10px;
}

.output{background:#fffaf0;padding:20px;border-radius:10px;margin-top:20px;}

.output-images{display:flex;gap:10px;margin-bottom:15px;}
.output-images img{
 width:48%;height:220px;object-fit:contain;background:#f5ecd9;border-radius:6px;
}

button{
 padding:10px 18px;background:#8b6f47;color:white;border:none;border-radius:6px;
}

.history-btn{
 margin-top:10px;
 padding:10px;
 background:#e5d7b5;
 border-radius:6px;
 cursor:pointer;
}

.panel{
 position:fixed;
 top:0;
 right:0;
 width:60%;
 height:100%;
 background:#fff;
 z-index:9999;
 padding:20px;
 overflow-y:auto;
 display:none;
 box-shadow:-5px 0 20px rgba(0,0,0,0.2);
}

.history-card{
 display:flex;
 gap:10px;
 margin-bottom:10px;
}

.history-card img{
 width:70px;
 height:70px;
 object-fit:cover;
 border-radius:6px;
}

#uploadWrapper.collapsed{
 display:none;
}

/* --- TABS --- */
.tabs{display:flex;gap:10px;margin-bottom:15px;}
.tab{padding:8px 12px;border-radius:6px;background:#e5d7b5;cursor:pointer;}
.tab.active{background:#8b6f47;color:#fff;}
.tab-content{display:none;}
.tab-content.active{display:block;}
#detailMap{height:300px;border-radius:10px;margin-top:10px;}

/* --- LOADER --- */
.loader{
 display:none;position:fixed;top:0;left:0;width:100%;height:100%;
 background:rgba(0,0,0,0.7);justify-content:center;align-items:center;
}

.loader-box{
 background:#fff;padding:30px;border-radius:12px;width:340px;
 box-shadow:0 10px 30px rgba(0,0,0,0.2);
}

.loader-title{font-weight:bold;margin-bottom:8px;}
.loader-sub{font-size:13px;color:#6b5c3e;margin-bottom:15px;}

.step{margin:6px 0;opacity:.4;font-size:13px;}
.step.active{opacity:1;font-weight:bold;}
.step.done::before{content:"✔ ";color:#8b6f47;}

.progress{height:8px;background:#ddd;margin-top:15px;border-radius:6px;}
.bar{height:100%;width:0;background:#8b6f47;border-radius:6px;}
</style>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

<script>
const steps=[
 "Uploading images",
 "Reading handwriting (OCR)",
 "Extracting postcard data",
 "Analyzing stamp",
 "Building story",
 "Finalizing"
];

let loaderInterval;

function startLoader(){
 document.getElementById("loader").style.display="flex";
 let s=document.getElementById("steps");
 s.innerHTML="";
 steps.forEach(x=>s.innerHTML+="<div class='step'>"+x+"</div>");

 let i=0;
 loaderInterval=setInterval(()=>{
   let el=document.querySelectorAll(".step");
   if(i<el.length){
     if(i>0){el[i-1].classList.remove("active");el[i-1].classList.add("done");}
     el[i].classList.add("active");
     document.getElementById("bar").style.width=
       Math.min(((i+1)/steps.length)*100,92)+"%";
     i++;
   }
 },900);
}

function stopLoader(){
 clearInterval(loaderInterval);
 document.getElementById("bar").style.width="100%";
 setTimeout(()=>{document.getElementById("loader").style.display="none";},300);
}


function previewImage(input,id){
 let file=input.files[0];
 if(!file) return;
 let r=new FileReader();
 r.onload=e=>document.getElementById(id).innerHTML=
   `<img src="${e.target.result}">`;
 r.readAsDataURL(file);
}

function switchTab(tab){
 document.querySelectorAll(".tab").forEach(t=>t.classList.remove("active"));
 document.querySelectorAll(".tab-content").forEach(c=>c.classList.remove("active"));
 document.getElementById("tab-"+tab).classList.add("active");
 document.getElementById("content-"+tab).classList.add("active");
 if(tab==="map"){ setTimeout(initDetailMap,100); }
}

let detailMap;
function initDetailMap(){
 if(!window.currentLat || !window.currentLon) return;
 if(detailMap){ detailMap.remove(); }

 detailMap = L.map('detailMap').setView([window.currentLat, window.currentLon], 6);
 L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png')
  .addTo(detailMap);
 L.marker([window.currentLat, window.currentLon]).addTo(detailMap);
}

async function deletePostcard(hash){
  if(!confirm("Delete this postcard?")) return;

  await fetch('/delete/' + hash, { method: 'DELETE' });

  refreshHistory();
}

async function submitForm(){
  startLoader();

  try {
    let fd = new FormData(document.getElementById("uploadForm"));
    let res = await fetch("/analyze", { method:"POST", body:fd });

    if(!res.ok){
      const text = await res.text();
      console.error(text);
      alert("Analysis failed - check console");
      stopLoader();
      return;
    }

    let data = await res.json();

    stopLoader();
    refreshHistory();
    document.getElementById("uploadWrapper").classList.add("collapsed");

    window.currentLat = data.lat;
    window.currentLon = data.lon;

    document.querySelector(".output").innerHTML = `
      <div class="output-images">
        <img src="data:image/jpeg;base64,${data.front}">
        <img src="data:image/jpeg;base64,${data.back}">
      </div>

      <div class="tabs">
        <div class="tab active" id="tab-overview" onclick="switchTab('overview')">Overview</div>
        <div class="tab" id="tab-story" onclick="switchTab('story')">Story</div>
        <div class="tab" id="tab-stamp" onclick="switchTab('stamp')">Stamp</div>
        <div class="tab" id="tab-map" onclick="switchTab('map')">Map</div>
      </div>

      <div id="content-overview" class="tab-content active">
        <p><b>Sender:</b> ${data.data.sender}</p>
        <p><b>Receiver:</b> ${data.data.receiver}</p>
        <p><b>Location:</b> ${data.data.location_sent_from}</p>
        <p><b>Date:</b> ${data.data.date}</p>
      </div>

      <div id="content-story" class="tab-content">
        <div style="white-space: pre-line;">${data.story}</div>
      </div>

      <div id="content-stamp" class="tab-content">
        <div style="white-space: pre-line;">${data.stamp}</div>
      </div>

      <div id="content-map" class="tab-content">
        <div id="detailMap"></div>
      </div>
    
    `;
    switchTab('overview');

  } catch(err){
    console.error(err);
    alert("Unexpected error");
    stopLoader();
  }
}


async function openHistory(){
  document.getElementById("panel").style.display="block";

  let res = await fetch("/history");
  let data = await res.json();
  window.historyData = data;

  let html = "";

  data.forEach((p, i) => {
    const sender = p.data?.sender || "Unknown";
    const location = p.data?.location_sent_from || "Unknown";
    const date = p.data?.date || "Unknown";

    html += `
      <div class="history-card">
        <img src="data:image/jpeg;base64,${p.front || ''}">
        
        <div style="flex:1;cursor:pointer;" onclick="loadPostcard(${i})">
          <b>${sender}</b><br>
          <span style="font-size:12px;color:#7a6a4f;">
            ${location} • ${date}
          </span>
        </div>

        <div style="cursor:pointer;color:red;font-weight:bold;padding:5px;"
             onclick="deletePostcard('${p.hash}')">✖</div>
      </div>
    `;
  });

  document.getElementById("panelContent").innerHTML = html;
}

async function refreshHistory(){
  let res = await fetch("/history");

  if(!res.ok){
    console.error("Failed to load history");
    return;
  }

  let data = await res.json();
  window.historyData = data;

  let html = "";

  data.forEach((p, i) => {
    const sender = p.data?.sender || "Unknown";
    const location = p.data?.location_sent_from || "Unknown";
    const date = p.data?.date || "Unknown";

    html += `
      <div class="history-card">
        <img src="data:image/jpeg;base64,${p.front || ''}">
        
        <div style="flex:1;cursor:pointer;" onclick="loadPostcard(${i})">
          <b>${sender}</b><br>
          <span style="font-size:12px;color:#7a6a4f;">
            ${location} • ${date}
          </span>
        </div>

        <div style="cursor:pointer;color:red;font-weight:bold;padding:5px;"
             onclick="deletePostcard('${p.hash}')">✖</div>
      </div>
    `;
  });

  document.getElementById("panelContent").innerHTML = html;
}

function closePanel(){
 document.getElementById("panel").style.display="none";
}

function newAnalysis(){
  // show upload again
  document.getElementById("uploadWrapper").classList.remove("collapsed");

  // clear output
  document.querySelector(".output").innerHTML = "";

  // reset previews
  document.getElementById("f").innerHTML = "";
  document.getElementById("b").innerHTML = "";

  // reset file inputs
  document.querySelector("input[name='front']").value = "";
  document.querySelector("input[name='back']").value = "";

  // reset map state
  window.currentLat = null;
  window.currentLon = null;
}

function loadPostcard(index){
  const p = window.historyData[index];
  if(!p) return;

  // restore map coords
  window.currentLat = p.lat;
  window.currentLon = p.lon;

  // close history panel
  document.getElementById("panel").style.display="none";

  // render postcard into main output (same structure as submitForm)
  document.querySelector(".output").innerHTML=`
    <div class="output-images">
      <img src="data:image/jpeg;base64,${p.front}">
      <img src="data:image/jpeg;base64,${p.back}">
    </div>

    <div class="tabs">
      <div class="tab active" id="tab-overview" onclick="switchTab('overview')">Overview</div>
      <div class="tab" id="tab-story" onclick="switchTab('story')">Story</div>
      <div class="tab" id="tab-stamp" onclick="switchTab('stamp')">Stamp</div>
      <div class="tab" id="tab-map" onclick="switchTab('map')">Map</div>
    </div>

    <div id="content-overview" class="tab-content active">
      <p><b>Sender:</b> ${p.data.sender}</p>
      <p><b>Receiver:</b> ${p.data.receiver}</p>
      <p><b>Location:</b> ${p.data.location_sent_from}</p>
      <p><b>Date:</b> ${p.data.date}</p>
    </div>

    <div id="content-story" class="tab-content">
      <div style="white-space: pre-line;">${p.story}</div>
    </div>

    <div id="content-stamp" class="tab-content">
      <div style="white-space: pre-line;">${p.stamp}</div>
    </div>

    <div id="content-map" class="tab-content">
      <div id="detailMap"></div>
    </div>
  `;
}

</script>

</head>
<body>

<div class="wrapper">
<div class="left">
<img src="/static/logo.png" class="logo">
<div class="tagline">Preserving history through postcards.</div>
<div class="history-btn" onclick="openHistory()">View History</div>
<div class="history-btn" onclick="newAnalysis()">New Analysis</div>
</div>

<div class="right">

<div id="uploadWrapper">
<form id="uploadForm">

<div class="upload-bar">

<div class="upload-card">
<div class="upload-title">Front of Card</div>
<div class="upload-sub">Click to upload</div>
<input type="file" name="front" onchange="previewImage(this,'f')" required>
<div id="f" class="preview"></div>
</div>

<div class="upload-card">
<div class="upload-title">Back of Card</div>
<div class="upload-sub">Click to upload</div>
<input type="file" name="back" onchange="previewImage(this,'b')" required>
<div id="b" class="preview"></div>
</div>

</div>

<button type="button" onclick="submitForm()">Analyze</button>
</form>
</div>

<div class="output"></div>
</div>

<div id="loader" class="loader">
<div class="loader-box">
<div class="loader-title">Analyzing your postcard</div>
<div class="loader-sub">Upload front & back images, then click Analyze</div>
<div id="steps"></div>
<div class="progress"><div id="bar" class="bar"></div></div>
</div>
</div>

<div id="panel" class="panel">
<button onclick="closePanel()">Close</button>
<div id="panelContent"></div>
</div>

</body>
</html>
"""

# --- ROUTES ---
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/delete/<hash_value>", methods=["DELETE"])
def delete(hash_value):
    delete_postcard_by_hash(hash_value)
    return jsonify({"status": "deleted"})

@app.route("/history")
def history():
    data = load_postcards()
    return jsonify(list(reversed(data)))

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        if "front" not in request.files or "back" not in request.files:
            return jsonify({"error": "Missing files"}), 400

        front_file = request.files["front"]
        back_file = request.files["back"]

        if front_file.filename == "" or back_file.filename == "":
            return jsonify({"error": "Empty file upload"}), 400

        f = front_file.read()
        b = back_file.read()

        # ✅ FIX: define these BEFORE using them
        f64 = encode_bytes(f)
        b64 = encode_bytes(b)

        # OCR
        ocr = client.responses.create(
            model="gpt-4.1",
            input=[{"role":"user","content":[
                {"type":"input_text","text":"Transcribe ALL visible text exactly. Preserve line breaks. Include handwriting."},
                {"type":"input_image","image_url":f"data:image/jpeg;base64,{f64}"},
                {"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"}
            ]}]
        )

        raw = ocr.output_text

        if not raw:
            return jsonify({"error": "OCR returned empty text"}), 500

        # --- PARSE ---
        parsed = client.responses.create(
            model="gpt-4.1",
            input=f"""
    Extract structured data from the postcard text.

    Return STRICT JSON only. No explanation.

    Format:
    {{
    "sender": "",
    "receiver": "",
    "location_sent_from": "",
    "date": ""
    }}

    TEXT:
    {raw}
    """
        )

        parsed_text = parsed.output_text
        data = safe_json(parsed_text)

        data = {
            "sender": clean_field(data.get("sender")),
            "receiver": clean_field(data.get("receiver")),
            "location_sent_from": clean_field(data.get("location_sent_from")),
            "date": clean_field(data.get("date"))
        }

        # STORY
        story = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
    Write clearly formatted sections:

    Context:
    Message Meaning:
    Historical Insight:
    Notable Details:

    TEXT:
    {raw}
    """
        ).output_text

        # STAMP
        stamp_resp = client.responses.create(
            model="gpt-4.1",
            input=[{
                "role":"user",
                "content":[
                    {"type":"input_text","text":"Analyze ONLY the postage stamp in the postcard image."},
                    {"type":"input_image","image_url":f"data:image/jpeg;base64,{f64}"},
                    {"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"}
                ]
            }]
        )

        stamp = stamp_resp.output_text.strip()
        if not stamp or len(stamp) < 5:
            stamp = "Unable to interpret"

        # GEO
        loc = data.get("location_sent_from")
        lat, lon = geocode(loc)

        # SAVE
        save_postcard({
            "hash": image_hash(f + b),
            "location": loc,
            "lat": lat,
            "lon": lon,
            "front": f64,
            "back": b64,
            "data": data,
            "story": story,
            "stamp": stamp
        })

        return jsonify({
            "data": data,
            "story": story,
            "stamp": stamp,
            "front": f64,
            "back": b64,
            "lat": lat,
            "lon": lon
        })
    except Exception as e:
        print("🔥 ANALYZE ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)