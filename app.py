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

  // wrap whole thing safely
  formatted = "<p>" + formatted + "</p>";

  // clean double paragraph breaks
  formatted = formatted.replace("<p></p>", "")

  return formatted;
}

function formatStamp(text){
  if(!text) return "";

  const sections = [
    "Country:",
    "Year:",
    "Denomination:",
    "Design:",
    "Historical Context:"
  ];

  let formatted = text;

  sections.forEach(section => {
    const title = section.replace(":", "");
    formatted = formatted.replaceAll(
      section,
      `</p><h3>${title}</h3><p>`
    );
  });

  formatted = "<p>" + formatted + "</p>";
  formatted = formatted.replace(/<p><\/p>/g, "");

  return formatted;
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
            <div class="stamp-body">
            ${formatStamp(data.stamp)}
            </div>
        </div>
        </div>

        <div id="content-map" class="tab-content">
        <div class="map-container">
            <div class="map-title">
                Postcard Origin — ${data.data.location_sent_from || "Unknown location"}
            </div>
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
  window.currentLat = p.lat;
  window.currentLon = p.lon;

  // close history panel
  document.getElementById("panel").style.display="none";

  // render postcard into main output (same structure as submitForm)
  document.querySelector(".output").innerHTML=`
    <div class="output-images">
    <div class="postcard-frame">
        <div class="postcard-label">Front</div>
        <img src="data:image/jpeg;base64,${p.front}"
            onclick="openModal(this.src)">
    </div>
    <div class="postcard-frame">
        <div class="postcard-label">Back</div>
        <img src="data:image/jpeg;base64,${p.back}"
            onclick="openModal(this.src)">
    </div>
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
    <div class="stamp-container">
        <div class="stamp-title">Stamp Analysis</div>
        <div class="stamp-body">
        ${formatStamp(data.stamp)}
        </div>
    </div>
    </div>

    <div id="content-map" class="tab-content">
    <div class="map-container">
        <div class="map-title">
            Postcard Origin — ${p.data.location_sent_from || "Unknown location"}
        </div>
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
    app.run(debug=True, port=5001)