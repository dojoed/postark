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
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Corrupted JSON file — resetting")
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


from PIL import Image, ImageChops
import io

def auto_crop_postcard(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Create background (assume corners represent background)
        bg = Image.new("RGB", img.size, img.getpixel((0, 0)))

        # Find difference
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()

        if not bbox:
            return image_bytes  # nothing to crop

        # --- ADD PADDING ---
        padding = 20  # pixels (tune 10–40)

        left = max(0, bbox[0] - padding)
        top = max(0, bbox[1] - padding)
        right = min(img.size[0], bbox[2] + padding)
        bottom = min(img.size[1], bbox[3] + padding)

        cropped = img.crop((left, top, right, bottom))

        buffer = io.BytesIO()
        cropped.save(buffer, format="JPEG")

        return buffer.getvalue()

    except Exception as e:
        print("Auto-crop error:", e)
        return image_bytes

from datetime import datetime

def parse_date_safe(date_str):
    try:
        return datetime.strptime(date_str, "%B %d, %Y")
    except:
        return datetime.min

from PIL import Image
import io

def normalize_orientation(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))

        width, height = img.size

        # If portrait → rotate to landscape
        if height > width:
            img = img.rotate(90, expand=True)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")

        return buffer.getvalue()

    except Exception as e:
        print("Orientation fix error:", e)
        return image_bytes  # fallback safely
    
def safe_json(t):
    try:
        if not t:
            return {}

        cleaned = t.replace("```json", "").replace("```", "").strip()

        # find first JSON object in string
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1

        if start == -1 or end == 0:
            print("No JSON object found:", t)
            return {}

        return json.loads(cleaned[start:end])

    except Exception:
        print("JSON parse error:", t)
        return {}
        
def clean_field(val):
    return val if val else "Unable to interpret"



def geocode(loc):
    try:
        if not loc or loc == "Unable to interpret":
            return None, None

        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": loc, "format": "json", "limit": 1},
            headers={"User-Agent": "postcard-app"},
            timeout=3
        ).json()

        if not r:
            print("Geocode no results:", loc)
            return None, None

        lat = float(r[0]["lat"])
        lon = float(r[0]["lon"])

        return lat, lon

    except Exception as e:
        print("Geocode error:", loc, e)
        return None, None

def detect_stamp_bbox(f64, b64):
    try:
        resp = client.responses.create(
            model="gpt-4.1",
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": """
Locate ONLY the postage stamp on this postcard.

STRICT REQUIREMENTS:
- The box must tightly fit ONLY the stamp edges (no background)
- Do NOT include surrounding postcard area
- The stamp is typically in the TOP RIGHT corner
- Ignore writing, addresses, and postmarks outside the stamp

Return STRICT JSON only:
{
  "x": <left>,
  "y": <top>,
  "width": <width>,
  "height": <height>
}

Coordinates must be normalized (0 to 1).
"""
                    },
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"}
                ]
            }]
        )

        data = safe_json(resp.output_text)

        try:
            x = float(data.get("x"))
            y = float(data.get("y"))
            w = float(data.get("width"))
            h = float(data.get("height"))
        except (TypeError, ValueError):
            print("❌ Invalid bbox data:", data)
            return None

        # validate bounds
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            print("Invalid bbox range:", data)
            return None

        # reject tiny boxes
        if w < 0.05 or h < 0.05:
            print("BBox too small:", data)
            return None

        return (x, y, w, h)

    except Exception as e:
        print("Stamp detection error:", e)
        return None

from PIL import Image, ImageDraw
import io

def crop_stamp(image_bytes, bbox):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size

        x, y, bw, bh = bbox

        padding = 0.08  # 8% padding (tune 0.05–0.15)

        x = max(0, x - padding)
        y = max(0, y - padding)
        bw = min(1 - x, bw + padding * 2)
        bh = min(1 - y, bh + padding * 2)

        left = int(x * w)
        top = int(y * h)
        right = int((x + bw) * w)
        bottom = int((y + bh) * h)

        cropped = img.crop((left, top, right, bottom))

        buffer = io.BytesIO()
        cropped.save(buffer, format="JPEG")

        return base64.b64encode(buffer.getvalue()).decode()
    except Exception as e:
        print("Crop error:", e)
        return None
    



def draw_bbox(image_bytes, bbox):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        draw = ImageDraw.Draw(img)

        w, h = img.size
        x, y, bw, bh = bbox

        left = int(x * w)
        top = int(y * h)
        right = int((x + bw) * w)
        bottom = int((y + bh) * h)

        # draw rectangle (red, thick)
        for i in range(3):
            draw.rectangle(
                [left-i, top-i, right+i, bottom+i],
                outline="red"
            )

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode()

    except Exception as e:
        print("Draw bbox error:", e)
        return None

import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

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
.left{
  width:26%;
  padding:28px 22px;
  background: linear-gradient(180deg, #efe3c2, #e6d6af);
  display:flex;
  flex-direction:column;
  gap:18px;
  border-right:1px solid #d8c79c;
}
.right{width:74%;padding:30px;overflow-y:auto;}

/* --- LOGO --- */
.logo{
  width:100%;
  margin-bottom:6px;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.15));
}

.tagline{
  font-size:13px;
  color:#6b5c3e;
  margin-bottom:10px;
  line-height:1.4;
}

/* --- NAV SECTION --- */
.nav-section{
  margin-top:10px;
}


/* --- BUTTON STYLE --- */
.nav-btn{
  display:flex;
  align-items:center;
  justify-content:space-between;

  padding:12px 14px;
  margin-bottom:10px;

  background:#fffdf6;
  border:1px solid #e2d3aa;
  border-radius:10px;

  font-size:14px;
  font-weight:600;
  color:#3e3625;

  cursor:pointer;
  transition: all 0.2s ease;
}



/* hover */
.nav-btn:hover{
  background:#f7efd9;
  transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
}

/* active press */
.nav-btn:active{
  transform: scale(0.98);
  box-shadow: none;
}

/* subtle arrow indicator */
.nav-btn::after{
  content:"→";
  font-size:14px;
  color:#8b6f47;
  opacity:0.7;
}

/* --- DIVIDER --- */
.nav-divider{
  height:1px;
  background:#dccb9c;
  margin:10px 0;
}

/* --- FOOTER (optional future use) --- */
.nav-footer{
  margin-top:auto;
  font-size:11px;
  color:#8a7a58;
  text-align:center;
}

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
.tabs{
  display:flex;
  gap:8px;
  margin-bottom:18px;
  border-bottom:1px solid #e0d2aa;
}

.tab{
  padding:10px 14px;
  cursor:pointer;
  color:#6b5c3e;
  position:relative;
  transition: all 0.2s ease;
}

/* hover effect */
.tab:hover{
  color:#3e3625;
}

/* underline animation */
.tab::after{
  content:"";
  position:absolute;
  left:0;
  bottom:-1px;
  width:0%;
  height:2px;
  background:#8b6f47;
  transition: width 0.25s ease;
}

/* active tab */
.tab.active{
  color:#3e3625;
  font-weight:bold;
}

.tab.active::after{
  width:100%;
}

.tab-content{
  display:block;
  opacity:0;
  transition: opacity 0.25s ease;
  height:0;
  overflow:hidden;
}

.tab-content.active{
  opacity:1;
  height:auto;
}
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
.bar{
  height:100%;
  width:0;
  background: linear-gradient(90deg, #8b6f47, #a98c5a);
  border-radius:6px;
  transition: width 0.4s ease;
}
.bar{height:100%;width:0;background:#8b6f47;border-radius:6px;}

/* --- STORY Styles --- */
.story-container{
  max-width: 720px;
  margin: 10px auto;
  line-height: 1.7;
  font-size: 16px;
  color: #3e3625;
  background: #fffdf6;
  padding: 20px 24px;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  border: 1px solid #e6d8b5;
}

.story-container h3{
  margin-top: 20px;
  margin-bottom: 8px;
  color: #8b6f47;
  font-size: 15px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  border-bottom: 1px solid #e6d8b5;
  padding-bottom: 4px;
}

.story-container p{
  margin: 8px 0 14px 0;
  line-height: 1.75;
}

.story-title{
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 12px;
  color: #5a4d36;
  border-bottom: 1px solid #e0d2aa;
  padding-bottom: 6px;
}

.story-body{
  font-size: 16px;
}

.overview-grid{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 10px;
}

.overview-item{
  background: #fffdf6;
  border: 1px solid #e6d8b5;
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
  transition: all 0.2s ease;
}

.overview-item:hover{
  transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
}

.overview-label{
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #9a8a6a;
  margin-bottom: 6px;
}

.overview-value{
  font-size: 16px;
  font-weight: 600;
  color: #2f281d;
}

.history-card{
  display:flex;
  gap:12px;
  margin-bottom:12px;
  padding:10px;
  border-radius:10px;
  background:#fffdf6;
  border:1px solid #e6d8b5;
  transition: all 0.2s ease;
}

.history-card:hover{
  background:#f9f2df;
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0,0,0,0.08);
}

.history-card img{
  width:70px;
  height:70px;
  object-fit:cover;
  border-radius:8px;
}

.history-meta{
  flex:1;
}

.history-sender{
  font-weight:bold;
  color:#3e3625;
}

.history-sub{
  font-size:12px;
  color:#7a6a4f;
  margin-top:2px;
}

.history-delete{
  color:#a94442;
  font-weight:bold;
  cursor:pointer;
  padding:5px;
}

.output-images{
  display:flex;
  gap:16px;
  margin-bottom:20px;
}

.postcard-frame{
  flex:1;
  background:#fffdf6;
  border:1px solid #e6d8b5;
  border-radius:10px;
  padding:10px;
  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
  transition: transform 0.2s ease;
}

.postcard-frame:hover{
  transform: scale(1.02);
}

.postcard-frame img{
  width:100%;
  height:240px;
  object-fit:contain;
  background:#f5ecd9;
  border-radius:6px;
}

.img-modal{
  display:none;
  position:fixed;
  top:0;
  left:0;
  width:100%;
  height:100%;
  background:rgba(0,0,0,0.85);
  justify-content:center;
  align-items:center;
  z-index:10000;
}

.img-modal img{
  max-width:90%;
  max-height:90%;
  border-radius:10px;
  box-shadow:0 10px 30px rgba(0,0,0,0.5);
  background:#fff;
  padding:10px;
}

.modal-content{
  position: relative;
}

.modal-close{
  position:absolute;
  top:-10px;
  right:-10px;
  background:#fff;
  border-radius:50%;
  width:28px;
  height:28px;
  display:flex;
  align-items:center;
  justify-content:center;
  font-weight:bold;
  cursor:pointer;
  box-shadow:0 2px 6px rgba(0,0,0,0.3);
}

.history-card{
  opacity:0;
  transform: translateY(10px);
  animation: fadeSlideIn 0.4s ease forwards;
}

@keyframes fadeSlideIn{
  to{
    opacity:1;
    transform: translateY(0);
  }
}

.loader-box{
  background:#fff;
  padding:30px;
  border-radius:12px;
  width:340px;
  box-shadow:0 10px 30px rgba(0,0,0,0.25);
  text-align:center;
}

/* title stronger */
.loader-title{
  font-weight:bold;
  font-size:16px;
  margin-bottom:6px;
}

/* subtle animation pulse */
.loader-box{
  animation: loaderPulse 1.5s ease-in-out infinite;
}

@keyframes loaderPulse{
  0%{transform: scale(1);}
  50%{transform: scale(1.02);}
  100%{transform: scale(1);}
}

#loaderMessage{
  font-size:13px;
  color:#8b6f47;
  margin-bottom:12px;
  font-style:italic;
  min-height:18px; /* prevents layout jump */
  transition: opacity 0.2s ease;
}

.map-container{
  background:#fffdf6;
  border:1px solid #e6d8b5;
  border-radius:10px;
  padding:12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.map-title{
  font-size:14px;
  font-weight:bold;
  color:#5a4d36;
  margin-bottom:8px;
}

.stamp-container{
  max-width: 720px;
  margin: 10px auto;
  background:#fffdf6;
  border:1px solid #e6d8b5;
  border-radius:10px;
  padding:18px 20px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.stamp-title{
  font-size:16px;
  font-weight:bold;
  color:#5a4d36;
  margin-bottom:10px;
  border-bottom:1px solid #e0d2aa;
  padding-bottom:6px;
}

.stamp-body{
  font-size:15px;
  line-height:1.6;
  color:#3e3625;
}


/* --- GLOBAL FADE-IN --- */
.fade-in{
  animation: fadeInUp 0.4s ease forwards;
}

@keyframes fadeInUp{
  from{
    opacity: 0;
    transform: translateY(8px);
  }
  to{
    opacity: 1;
    transform: translateY(0);
  }
}

/* --- TAB TRANSITION SMOOTHER --- */
.tab-content{
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.tab-content.active{
  opacity:1;
  transform: translateY(0);
}

.tab-content:not(.active){
  transform: translateY(6px);
}

/* --- CARD HOVER IMPROVEMENT --- */
.postcard-frame{
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.postcard-frame:hover{
  transform: scale(1.02);
  box-shadow: 0 10px 22px rgba(0,0,0,0.12);
}

.postcard-frame{
  position: relative; /* REQUIRED for overlay */
}

.postcard-label{
  position: absolute;
  top: 10px;
  left: 10px;

  background: rgba(255, 253, 246, 0.9);
  backdrop-filter: blur(4px);

  padding: 4px 10px;
  border-radius: 6px;

  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;

  color: #5a4d36;
  border: 1px solid #e6d8b5;

  box-shadow: 0 2px 6px rgba(0,0,0,0.1);

  pointer-events: none; /* don’t block clicks */
}

/* --- STAMP LAYOUT --- */
.stamp-layout{
  display:grid;
  grid-template-columns: 140px 1fr;
  gap:20px;
  align-items:start;
}

/* --- STAMP IMAGE --- */
.stamp-image{
  width:140px;
  height:140px;

  object-fit:cover;
  object-position: top right;

  border-radius:10px;
  border:1px solid #e6d8b5;
  background:#fff;

  padding:8px;

  box-shadow: 0 6px 14px rgba(0,0,0,0.08);
  transition: transform 0.2s ease;
}

.stamp-image:hover{
  transform: scale(1.05);
}

/* --- STAMP TEXT --- */
.stamp-body p{
  margin: 6px 0 12px 0;
}

.stamp-body{
  font-size:14px;
  line-height:1.7;
  color:#3e3625;
}

/* better section headers */
.stamp-section{
  margin-top:16px;
  margin-bottom:6px;

  font-size:11px;
  font-weight:bold;
  letter-spacing:0.6px;
  text-transform:uppercase;

  color:#8b6f47;

  border-bottom:1px solid #e6d8b5;
  padding-bottom:3px;
}

</style>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-rotatedmarker/leaflet.rotatedMarker.js"></script>

<script>
const steps=[
 "Uploading images",
 "Reading handwriting (OCR)",
 "Extracting postcard data",
 "Analyzing stamp",
 "Building story",
 "Finalizing"
];

const messages = [
  "Preparing images...",
  "Reading handwriting...",
  "Extracting key details...",
  "Inspecting stamp...",
  "Building historical context...",
  "Finalizing results..."
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
   
   const msg = document.getElementById("loaderMessage");
   if(msg) msg.innerText = messages[i] || "";
   
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
 if(tab==="map"){
  setTimeout(() => {
    initDetailMap();
    if(detailMap) detailMap.invalidateSize();
  }, 200);
}
}



let detailMap;
function initDetailMap(){
  if(!window.currentLat || !window.currentLon) return;

  if(detailMap){ detailMap.remove(); }

  detailMap = L.map('detailMap').setView([window.currentLat, window.currentLon], 4);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png')
    .addTo(detailMap);

  // --- ORIGIN (sender) ---
  const from = [window.currentLat, window.currentLon];
  L.marker(from).addTo(detailMap).bindPopup("Sent from");

  // --- DESTINATION (receiver) ---
  if(window.currentLatTo && window.currentLonTo){
    const to = [window.currentLatTo, window.currentLonTo];

    const bounds = L.latLngBounds([from, to]);
    detailMap.fitBounds(bounds, { padding: [30,30] });

    L.marker(to).addTo(detailMap).bindPopup("Sent to");

    // --- DRAW LINE ---
    // --- CURVED ARC ---
    function createArc(from, to, offset = 0.3, steps = 50){
    const latlngs = [];

    for(let i = 0; i <= steps; i++){
        const t = i / steps;

        // linear interpolation
        const lat = from[0] + (to[0] - from[0]) * t;
        const lon = from[1] + (to[1] - from[1]) * t;

        // add curve (sine wave offset)
        const curve = Math.sin(Math.PI * t) * offset;

        latlngs.push([
        lat + curve,
        lon
        ]);
    }

    return latlngs;
    }

    const arcPoints = createArc(from, to);

    // moving marker (postcard travel)
    const postcardIcon = L.icon({
    iconUrl: 'https://cdn-icons-png.flaticon.com/512/1048/1048945.png',
    iconSize: [32, 32],
    iconAnchor: [16, 16]
    });


    const travelMarker = L.marker(arcPoints[0], {
    icon: postcardIcon,
    rotationAngle: 0
    }).addTo(detailMap);

    // start with empty line
    const line = L.polyline([], {
    color: '#8b6f47',
    weight: 4,
    opacity: 0.8
    }).addTo(detailMap);

    const glowLine = L.polyline([], {
    color: '#cbb892',
    weight: 8,
    opacity: 0.3
    }).addTo(detailMap);

    // animate drawing
    let i = 0;
    const speed = 30; // lower = faster

    function drawLine(){
  if(i < arcPoints.length){
    const point = arcPoints[i];

    // draw line
    line.addLatLng(point);
    glowLine.addLatLng(point);

    // rotate marker (AFTER first point)
    if(i > 0){
    const prev = arcPoints[i - 1];
    const angle = Math.atan2(
    point[0] - prev[0],
    point[1] - prev[1]
    ) * (180 / Math.PI);

    // SAFE check
    if(travelMarker.setRotationAngle){
        travelMarker.setRotationAngle(angle);
    }
    }

    // move marker
    travelMarker.setLatLng(point);

    i++;
    setTimeout(drawLine, speed);
  }
}

    drawLine();

    // auto-fit both points

    
        } else {
    // fallback: just center origin
    detailMap.setView(from, 6);
  }
}

async function openTimeline(){
  document.getElementById("panel").style.display="block";

  // ONLY load raw history data (no rendering)
  let historyRes = await fetch("/history");
  window.historyData = await historyRes.json();

  let res = await fetch("/timeline");
  let data = await res.json();

  let html = `
<div style="
  display:flex;
  align-items:flex-start;
  overflow-x:auto;
  padding:40px 30px;
  gap:60px;
  position:relative;
">

  <!-- timeline line -->
  <div style="
    position:absolute;
    top:60px;
    left:0;
    right:0;
    height:3px;
    background:linear-gradient(90deg,#e6d8b5,#cbb892,#e6d8b5);
  "></div>
`;

  data.forEach((group, index) => {

  html += `
  <div style="
    min-width:200px;
    text-align:center;
    position:relative;
    z-index:2;
  ">

    <!-- YEAR -->
    <div style="
      font-weight:bold;
      font-size:18px;
      margin-bottom:12px;
      color:#5a4d36;
    ">
      ${group.year}
    </div>

    <!-- DOT -->
    <div style="
      width:14px;
      height:14px;
      background:#8b6f47;
      border-radius:50%;
      margin:0 auto 20px auto;
      box-shadow:0 0 0 4px #f5ecd9;
    "></div>

    <!-- STACKED CARDS -->
    <div style="
      display:flex;
      flex-direction:column;
      gap:10px;
      align-items:center;
    ">
  `;

  group.items.forEach((p, i) => {
    html += `
      <img 
        class="timeline-item"
        src="data:image/jpeg;base64,${p.front}"
        onclick="highlightTimeline(this); loadPostcardFromTimeline('${p.hash}')"
        style="
          width:${80 - i*5}px;
          height:${80 - i*5}px;
          object-fit:cover;
          border-radius:8px;
          cursor:pointer;
          border:1px solid #e6d8b5;

          transform: rotate(${(i%2===0? -2:2)}deg);
          transition: all 0.25s ease;
        "

          onmouseover="if(this.style.opacity !== '1'){ this.style.transform='scale(1.1)' }"
          onmouseout="if(this.style.opacity !== '1'){ this.style.transform='scale(1)' }"
      >
    `;
  });

  html += `
    </div>
  </div>
  `;
});

  html += `</div>`;

  document.getElementById("panelContent").innerHTML = html;
}

async function deletePostcard(hash){
  if(!confirm("Delete this postcard?")) return;

  await fetch('/delete/' + hash, { method: 'DELETE' });

  refreshHistory();
}

function formatStory(text){
  if(!text) return "";

  const sections = [
    "Context:",
    "Message Meaning:",
    "Historical Insight:",
    "Notable Details:"
  ];

  let formatted = text;

  sections.forEach(section => {
    const title = section.replace(":", "");

    formatted = formatted.replaceAll(
      section,
      `</p><h3>${title}</h3><p>`
    );
  });

  // wrap safely
  formatted = "<p>" + formatted + "</p>";

  // clean empty paragraphs
  formatted = formatted.replace(/<p>\s*<\/p>/g, "");

  return formatted;
}

function openRestoration(){
  document.getElementById("uploadWrapper").classList.add("collapsed");

  document.querySelector(".output").innerHTML = `
    <div class="fade-in">

      <h2 style="margin-bottom:10px;">Digital Restoration</h2>

      <div class="upload-card" style="max-width:400px;">
        <div class="upload-title">Upload Postcard Image</div>
        <div class="upload-sub">We’ll enhance and restore it</div>
        <input type="file" id="restoreFile" onchange="previewImage(this,'restorePreview')">
        <div id="restorePreview" class="preview"></div>
      </div>

      <button onclick="restoreImage()" style="margin-top:15px;">
        Restore Image
      </button>

      <div id="restoreOutput" style="margin-top:20px;"></div>

    </div>
  `;
}


function renderPostcardImages(front, back){
  return `
    <div class="output-images">
      <div class="postcard-frame">
        <div class="postcard-label">Front</div>
        <img src="data:image/jpeg;base64,${front}" onclick="openModal(this.src)">
      </div>
      <div class="postcard-frame">
        <div class="postcard-label">Back</div>
        <img src="data:image/jpeg;base64,${back}" onclick="openModal(this.src)">
      </div>
    </div>
  `;
}

function renderTabs(){
  return `
    <div class="tabs">
      <div class="tab active" id="tab-overview" onclick="switchTab('overview')">Overview</div>
      <div class="tab" id="tab-story" onclick="switchTab('story')">Story</div>
      <div class="tab" id="tab-stamp" onclick="switchTab('stamp')">Stamp</div>
      <div class="tab" id="tab-map" onclick="switchTab('map')">Map</div>
      <div class="tab" id="tab-appraisal" onclick="switchTab('appraisal')">Appraisal</div>
    </div>
  `;
}

function renderOverview(data){
  return `
    <div id="content-overview" class="tab-content active">
      <div class="overview-grid">
        <div class="overview-item">
          <div class="overview-label">Sender</div>
          <div class="overview-value">${data.sender}</div>
        </div>

        <div class="overview-item">
          <div class="overview-label">Receiver</div>
          <div class="overview-value">${data.receiver}</div>
        </div>

        <div class="overview-item">
          <div class="overview-label">Location</div>
          <div class="overview-value">${data.location_sent_from}</div>
        </div>

        <div class="overview-item">
          <div class="overview-label">Date</div>
          <div class="overview-value">${data.date}</div>
        </div>
      </div>
    </div>
  `;
}

function renderStamp(stamp, image){
  return `
    <div id="content-stamp" class="tab-content">
      <div class="stamp-container">
        <div class="stamp-title">Stamp Analysis</div>

        <div class="stamp-layout">
          <img src="data:image/jpeg;base64,${image}"
            style="width:120px;height:120px;object-fit:cover;
                   object-position: top right;
                   border:1px solid #e6d8b5;
                   border-radius:8px;
                   padding:6px;
                   background:#fff;">

          <div class="stamp-body" style="white-space: pre-line; flex:1;">
            ${stamp}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderImages(front, back){
  return `
    <div class="output-images">
      <div class="postcard-frame">
        <div class="postcard-label">Front</div>
        <img src="data:image/jpeg;base64,${front}">
      </div>
      <div class="postcard-frame">
        <div class="postcard-label">Back</div>
        <img src="data:image/jpeg;base64,${back}">
      </div>
    </div>
  `;
}

function formatStamp(text){
  if(!text) return "";

  let cleaned = text;

  // remove markdown artifacts
  cleaned = cleaned.replace(/###/g, "");
  cleaned = cleaned.replace(/---/g, "");
  cleaned = cleaned.replace(/\*\*/g, "");

  // remove intro fluff
  cleaned = cleaned.replace(/Certainly!.*analysis of the postage stamp.*:/i, "");

  // normalize bullets
  cleaned = cleaned.replace(/- /g, "");

  // section headers
  const sections = [
    "Identification",
    "Design Details",
    "Historical Context",
    "Condition Assessment",
    "Rarity & Value Insight",
    "Summary"
  ];

  sections.forEach(section => {
    const regex = new RegExp(section + "\\s*:?","gi");

    cleaned = cleaned.replace(
      regex,
      `</p><h4 class="stamp-section">${section}</h4><p>`
    );
  });

  // wrap paragraphs
  cleaned = "<p>" + cleaned + "</p>";

  // cleanup empty tags
  cleaned = cleaned.replace(/<p>\s*<\/p>/g, "");

  return cleaned.trim();
}

async function submitForm(){
  startLoader();

  // show images immediately for perceived speed
const frontPreview = document.getElementById("f").innerHTML;
const backPreview = document.getElementById("b").innerHTML;

document.querySelector(".output").innerHTML = `
<div class="fade-in">
    <div class="postcard-frame">
      <div class="postcard-label">Front</div>
      ${frontPreview}
    </div>
    <div class="postcard-frame">
      <div class="postcard-label">Back</div>
      ${backPreview}
    </div>
  </div>
`;

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

    window.currentLat = data.lat_from;
    window.currentLon = data.lon_from;
    window.currentLatTo = data.lat_to;
    window.currentLonTo = data.lon_to;

    document.querySelector(".output").innerHTML = `
    <div class="output-images">
    <div class="postcard-frame">
        <div class="postcard-label">Front</div>
            <img src="data:image/jpeg;base64,${data.front}"
            onclick="openModal(this.src)">
    </div>
    <div class="postcard-frame">
        <div class="postcard-label">Back</div>
        <img src="data:image/jpeg;base64,${data.back}"
            onclick="openModal(this.src)">
        </div>
    </div>

        <div class="tabs">
        <div class="tab active" id="tab-overview" onclick="switchTab('overview')">Overview</div>
        <div class="tab" id="tab-story" onclick="switchTab('story')">Story</div>
        <div class="tab" id="tab-stamp" onclick="switchTab('stamp')">Stamp</div>
        <div class="tab" id="tab-appraisal" onclick="switchTab('appraisal')">Appraisal</div>
        <div class="tab" id="tab-map" onclick="switchTab('map')">Map</div>
        </div>

            <div id="content-overview" class="tab-content active">
                <div class="overview-grid">

            <div class="overview-item">
            <div class="overview-label">Sender</div>
            <div class="overview-value">${data.data.sender}</div>
            </div>

            <div class="overview-item">
            <div class="overview-label">Receiver</div>
            <div class="overview-value">${data.data.receiver}</div>
            </div>

            <div class="overview-item">
            <div class="overview-label">Location</div>
            <div class="overview-value">${data.data.location_sent_from}</div>
            </div>

            <div class="overview-item">
            <div class="overview-label">Date</div>
            <div class="overview-value">${data.data.date}</div>
            </div>

        </div>
        </div>

      <div id="content-story" class="tab-content">
        <div class="story-container">
            <div class="story-title">Postcard Analysis</div>
            <div class="story-body">
                ${formatStory(data.story)}
            </div>
        </div>
      </div>


      

      
<div id="content-stamp" class="tab-content">
  <div class="stamp-container">

    <div class="stamp-title">Stamp Analysis</div>

    <div style="display:flex; gap:20px; align-items:flex-start;">

            <img class="stamp-image" src="data:image/jpeg;base64,${data.stamp_image || data.back}"
           style="width:120px;height:120px;object-fit:cover;
                  object-position: top right;
                  border:1px solid #e6d8b5;
                  border-radius:8px;
                  padding:6px;
                  background:#fff;">

      <div class="stamp-body" style="white-space: pre-line; flex:1;">
        ${formatStamp(data.stamp)}
      </div>

    </div>

  </div>
</div>


<div id="content-appraisal" class="tab-content">
  <div class="stamp-container">
    <div class="stamp-title">Postcard Appraisal</div>

    <div class="stamp-body">
      ${renderAppraisal(data.appraisal)}
    </div>
  </div>
</div>

        <div id="content-map" class="tab-content">
        <div class="map-container">
            <div class="map-title">
                ${data.data.location_sent_from || "Unknown"} 
                → 
                ${data.data.location_sent_to || "Unknown"}
            </div>

            ${data.distance_km ? `
            <div style="font-size:13px;color:#7a6a4f;margin-bottom:8px;">
                Distance traveled: ${data.distance_km} km
            </div>
        ` : ""}
            <div id="detailMap"></div>
        </div>
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
    const delay = i * 0.05;
    const sender = p.data?.sender || "Unknown";
    const location = p.data?.location_sent_from || "Unknown";
    const date = p.data?.date || "Unknown";

    html += `
      <div class="history-card">
        <img src="data:image/jpeg;base64,${p.front || ''}">
        
        <div class="history-meta" onclick="loadPostcard(${i})">
        <div class="history-sender">${sender}</div>
        <div class="history-sub">${location} • ${date}</div>
    </div>

    <div class="history-delete"
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
    const delay = i * 0.05;
    const sender = p.data?.sender || "Unknown";
    const location = p.data?.location_sent_from || "Unknown";
    const date = p.data?.date || "Unknown";

    html += `
      <div class="history-card" style="animation-delay:${delay}s">
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
    window.currentLat = p.lat_from;
    window.currentLon = p.lon_from;
    window.currentLatTo = p.lat_to;
    window.currentLonTo = p.lon_to;

  // close history panel
  document.getElementById("panel").style.display="none";

  // render postcard into main output (same structure as submitForm)
  document.querySelector(".output").innerHTML=`
    <div class="output-images">
    <div class="postcard-frame">
        <div class="postcard-label">Front</div>
        <img src="data:image/jpeg;base64,${p.front || ''}"
            onclick="openModal(this.src)">
    </div>
    <div class="postcard-frame">
        <div class="postcard-label">Back</div>
        <img src="data:image/jpeg;base64,${p.back || ''}"            
                onclick="openModal(this.src)">
    </div>
    </div>

    <div class="tabs">
      <div class="tab active" id="tab-overview" onclick="switchTab('overview')">Overview</div>
      <div class="tab" id="tab-story" onclick="switchTab('story')">Story</div>
      <div class="tab" id="tab-stamp" onclick="switchTab('stamp')">Stamp</div>
      <div class="tab" id="tab-appraisal" onclick="switchTab('appraisal')">Postcard Appraisal</div>
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
    <div class="stamp-container">

    <div class="stamp-title">Stamp Analysis</div>

    <div style="display:flex; gap:20px; align-items:flex-start;">

      <!-- stamp preview (top-right crop) -->
            <img src="data:image/jpeg;base64,${p.stamp_image || p.back}"
           style="width:120px;height:120px;object-fit:cover;
                  object-position: top right;
                  border:1px solid #e6d8b5;
                  border-radius:8px;
                  padding:6px;
                  background:#fff;">

      <!-- analysis -->
      <div class="stamp-body" style="white-space: pre-line; flex:1;">
        ${formatStamp(p.stamp)}
      </div>

    </div>

  </div>
</div>

<div id="content-appraisal" class="tab-content">
  <div class="stamp-container">
    <div class="stamp-title">Appraisal</div>

    <div class="stamp-body">
      ${renderAppraisal(p.appraisal)}
    </div>
  </div>
</div>

    <div id="content-map" class="tab-content">
    <div class="map-container">
        <div class="map-title">
            ${p.data.location_sent_from || "Unknown"} 
            → 
            ${p.data.location_sent_to || "Unknown"}
        </div>

        ${p.distance_km ? `
        <div style="font-size:13px;color:#7a6a4f;margin-bottom:8px;">
            Distance traveled: ${p.distance_km} km
        </div>
        ` : ""}
        <div id="detailMap"></div>
    </div>
    </div>
  `;
}

function openModal(src){
  const modal = document.getElementById("imageModal");
  const img = document.getElementById("modalImg");

  img.src = src;
  modal.style.display = "flex";
}

function closeModal(){
  document.getElementById("imageModal").style.display = "none";
}

function loadPostcardFromTimeline(hash){
  const p = window.historyData.find(x => x.hash === hash);
  if(p){
    loadPostcard(window.historyData.indexOf(p));
  }
}


async function clearHistory(){
  const confirmed = confirm("⚠️ This will permanently delete ALL postcards. Continue?");
  if(!confirmed) return;

  try {
    let res = await fetch("/clear", { method: "DELETE" });

    if(!res.ok){
      console.error("Clear failed:", res.status);
      alert("Failed to clear history");
      return;
    }

    // reset UI state
    window.historyData = [];

    document.getElementById("panelContent").innerHTML = `
      <div style="padding:20px;color:#7a6a4f;">
        No postcards yet.
      </div>
    `;

    document.querySelector(".output").innerHTML = "";

    alert("History cleared");

  } catch(e){
    console.error("Clear error:", e);
    alert("Unexpected error clearing history");
  }
}

function renderAppraisal(text){
  if(!text) return "";

  let cleaned = text;

  const sections = [
    "Estimated Value",
    "Confidence",
    "Key Value Drivers",
    "Rarity",
    "Condition Impact",
    "Collector Appeal"
  ];

  sections.forEach(section => {
    const regex = new RegExp(section + "\\s*:?","gi");

    cleaned = cleaned.replace(
      regex,
      `</p><h4 class="stamp-section">${section}</h4><p>`
    );
  });

  cleaned = "<p>" + cleaned + "</p>";
  cleaned = cleaned.replace(/<p>\s*<\/p>/g, "");

  return cleaned;
}

function highlightTimeline(el){
  document.querySelectorAll(".timeline-item").forEach(e=>{
    e.style.opacity = 0.4;
    e.style.transform = "scale(0.95)";
  });

  el.style.opacity = 1;
  el.style.transform = "scale(1.1)";
}

</script>



</head>
<body>

<div class="wrapper">
<div class="left">
<img src="/static/logo.png" class="logo">
<div class="tagline">Preserving history through postcards.</div>
<div class="nav-section">
  <div class="nav-btn" onclick="newAnalysis()">Analyze Postcards</div>
  <div class="nav-btn" onclick="openHistory()">View My Postcards</div>
  <div class="nav-btn" onclick="openTimeline()">Postcard Timeline</div>
  <div class="nav-btn" onclick="openRestoration()">Restore Postcard</div>
  <div class="nav-btn" onclick="clearHistory()">Clear All History</div>
</div>

<div class="nav-divider"></div>

<div class="nav-footer">
  v1.0 • Postcard Archaeology
</div>
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
<div id="loaderMessage" style="font-size:13px;color:#7a6a4f;margin-bottom:10px;"></div>
<div id="steps"></div>
<div class="progress"><div id="bar" class="bar"></div></div>
</div>
</div>

<div id="panel" class="panel">
<button onclick="closePanel()">Close</button>
<div id="panelContent"></div>
</div>

<div id="imageModal" class="img-modal" onclick="if(event.target === this) closeModal()">
  <div class="modal-content">
    <span class="modal-close" onclick="closeModal()">✕</span>
    <img id="modalImg">
  </div>
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

@app.route("/timeline")
def timeline():
    try:
        data = load_postcards()
        grouped = {}

        for p in data:
            pdata = p.get("data") or {}
            date_str = pdata.get("date") or ""

            dt = parse_date_safe(date_str)
            year = dt.year if dt.year > 1 else "Unknown"

            if year not in grouped:
                grouped[year] = []

            # ✅ ONLY send what frontend needs
            grouped[year].append({
                "hash": p.get("hash"),
                "front": p.get("front")
            })

        timeline_data = [
            {"year": y, "items": grouped[y]}
            for y in sorted(grouped.keys(), key=lambda x: str(x))
        ]

        return jsonify(timeline_data)

    except Exception as e:
        print("🔥 TIMELINE ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["DELETE"])
def clear_all():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump([], f)

        return jsonify({"status": "cleared"})
    except Exception as e:
        print("🔥 CLEAR ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
    
@app.route("/restore", methods=["POST"])
def restore():
    try:
        if "image" not in request.files:
            return jsonify({"error": "Missing image"}), 400

        file = request.files["image"]
        img_bytes = file.read()
        img_b64 = encode_bytes(img_bytes)

        # --- RESTORATION PROMPT ---
        resp = client.images.generate(
            model="gpt-image-1",
            prompt="""
Restore this vintage postcard image.

Goals:
- Remove stains, creases, discoloration
- Enhance faded ink and colors
- Preserve original details and authenticity
- Do NOT modernize or alter content
- Keep it historically accurate

Return a clean restored version of the SAME image.
""",
            size="1024x1024",
            image=img_b64
        )

        restored = resp.data[0].b64_json

        return jsonify({
            "original": img_b64,
            "restored": restored
        })

    except Exception as e:
        print("🔥 RESTORE ERROR:", str(e))
        return jsonify({"error": str(e)}), 500
        

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        print("🚀 ANALYZE STARTED")
        print("Files received:", list(request.files.keys()))
        if "front" not in request.files or "back" not in request.files:
            return jsonify({"error": "Missing files"}), 400

        front_file = request.files["front"]
        back_file = request.files["back"]

        if front_file.filename == "" or back_file.filename == "":
            return jsonify({"error": "Empty file upload"}), 400

        f = auto_crop_postcard(normalize_orientation(front_file.read()))
        b = auto_crop_postcard(normalize_orientation(back_file.read()))

        # ✅ FIX: define these BEFORE using them
        f64 = encode_bytes(f)
        b64 = encode_bytes(b)

        # --- STAMP DETECTION + CROP ---
        bbox = detect_stamp_bbox(f64, b64)
        stamp_img = None
        debug_bbox_img = None  # ✅ ALWAYS define it

        if bbox:
          print("✅ BBOX DETECTED:", bbox)

          debug_bbox_img = draw_bbox(b, bbox)

          stamp_img = crop_stamp(b, bbox)

          if not stamp_img:
              print("❌ Crop failed")
              stamp_img = None
          elif len(stamp_img) < 1000:
              print("⚠️ Crop too small, ignoring")
              stamp_img = None
        else:
            print("⚠️ No bbox detected")
            
        # OCR
        ocr = client.responses.create(
            model="gpt-4.1",
            input=[{"role":"user","content":[
                {"type":"input_text","text":"Transcribe ALL visible text exactly. Preserve line breaks. Include handwriting."},
                {"type":"input_image","image_url":f"data:image/jpeg;base64,{f64}"},
                {"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"}
            ]}]
        )

        raw = getattr(ocr, "output_text", None)

        if not raw:
            print("OCR RAW RESPONSE:", ocr)
            return jsonify({"error": "OCR returned empty text"}), 500


        # --- PARSE ---
        parsed = client.responses.create(
    model="gpt-4.1",
    input=f"""
Extract structured data from the postcard text.

Return STRICT JSON only. No explanation.

Identify:
- sender (person writing)
- receiver (person receiving)
- location_sent_from (where postcard was sent from)
- location_sent_to (destination city/state/country if present)
- date

Format:
    {{
    "sender": "",
    "receiver": "",
    "location_sent_from": "",
    "location_sent_to": "",
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
            "location_sent_to": clean_field(data.get("location_sent_to")),
            "date": clean_field(data.get("date"))
        }

        # STORY
        story = client.responses.create(
        model="gpt-4.1-mini",
        input=f"""
    You are a historical analyst interpreting a vintage postcard.

    Write clearly formatted sections using these exact headers:

    Context:
    Message Meaning:
    Historical Insight:
    Notable Details:

    Guidelines:
    - Be specific, not generic
    - Infer plausible historical and social context when possible
    - Keep tone natural and engaging (not robotic)
    - Avoid repeating the text verbatim
    - Add depth where information is limited (educated inference is encouraged)

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
                    {
                        "type":"input_text",
                        "text": """
        You are a philatelist (stamp expert).

        Analyze ONLY the postage stamp in this postcard.

        Return clean plain text only.

    DO NOT include:
    - markdown
    - bullet symbols
    - introductory phrases

    Use this exact structure:

    Identification:
    Country:
    Year:
    Denomination:

    Design Details:
    ...

    Historical Context:
    ...

    Condition Assessment:
    ...

    Rarity & Value Insight:
    ...

    Summary:
    ...
        """
                    },
                    {"type":"input_image","image_url":f"data:image/jpeg;base64,{stamp_img or b64}"}                ]
            }]
        )

        stamp = stamp_resp.output_text.strip()
        if not stamp or len(stamp) < 5:
            stamp = "Unable to interpret"

        # GEO
        loc_from = data.get("location_sent_from")
        loc_to = data.get("location_sent_to")

        lat_from, lon_from = (None, None)
        lat_to, lon_to = (None, None)

        if loc_from and loc_from != "Unable to interpret":
            lat_from, lon_from = geocode(loc_from)

        if loc_to and loc_to != "Unable to interpret":
            lat_to, lon_to = geocode(loc_to)
        # --- DISTANCE ---
        distance_km = None

        if lat_from and lon_from and lat_to and lon_to:
            distance_km = round(haversine(lat_from, lon_from, lat_to, lon_to), 1)

        appraisal_resp = client.responses.create(
    model="gpt-4.1",
    input=f"""
You are an expert in vintage postcard collecting and historical ephemera.

IMPORTANT:
You are appraising the ENTIRE postcard, not just the stamp.

Evaluate the postcard based on:
- age and era
- subject matter (location, theme, imagery)
- uniqueness of message or handwriting
- historical relevance
- condition (inferred if needed)
- stamp and postmark (as supporting signals only)

Return clean plain text using this EXACT structure:

Estimated Value:
$X - $Y USD

Confidence:
Low / Medium / High

Postcard Type:
(e.g. linen era, photo postcard, tourist, holiday, etc.)

Key Value Drivers:
...

Rarity:
...

Condition Impact:
...

Collector Appeal:
...

Summary:
...

Guidelines:
- Most postcards are low value ($1–$15) unless clearly rare
- Be conservative and realistic
- Do NOT overvalue common tourist postcards
- Only assign higher value if strong justification exists

DATA:
Sender: {data.get("sender")}
Location: {data.get("location_sent_from")}
Date: {data.get("date")}

MESSAGE:
{raw}

STAMP (secondary signal):
{stamp}

STORY CONTEXT:
{story}
"""
)


        appraisal = appraisal_resp.output_text.strip()

        # SAVE
        save_postcard({
            "hash": image_hash(f + b),
            "location": loc_from,
            "lat_from": lat_from,
            "lon_from": lon_from,
            "lat_to": lat_to,
            "lon_to": lon_to,
            "front": f64,
            "back": b64,
            "data": data,
            "story": story,
            "stamp": stamp,
            "stamp_image": stamp_img,
            "distance_km": distance_km,
            "appraisal": appraisal,
            "debug_bbox": debug_bbox_img   # 👈 ADD THIS LINE

        })

        return jsonify({
            "data": data,
            "story": story,
            "stamp": stamp,
            "front": f64,
            "back": b64,
            "lat_from": lat_from,
            "lon_from": lon_from,
            "lat_to": lat_to,
            "lon_to": lon_to,
            "appraisal": appraisal,
            "distance_km": distance_km,
            "stamp_image": stamp_img
        })
    except Exception as e:
        print("🔥 ANALYZE ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)