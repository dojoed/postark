import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
import json
from serpapi import GoogleSearch
from PIL import Image

# --- CONFIG ---
st.set_page_config(page_title="PostArk", page_icon="📬", layout="wide")

# --- STYLE ---
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: #f4f1ea;
}

.brand { text-align:center; padding-top:40px; }
.brand img { width:150px; }

.results { max-width:1000px; margin:40px auto; }

.card {
    background:white;
    border:1px solid #ddd;
    border-radius:10px;
    padding:20px;
    margin-bottom:20px;
    box-shadow:0 2px 6px rgba(0,0,0,0.05);
}

.info-card {
    background:white;
    border:1px solid #ddd;
    border-radius:10px;
    padding:15px;
    text-align:center;
}

.label {
    font-size:12px;
    color:#777;
    text-transform:uppercase;
}

.value {
    font-size:18px;
    font-weight:600;
}

.conf {
    font-size:11px;
    color:#aaa;
}

/* STORY */
.story {
    font-size:18px;
    line-height:1.8;
}
</style>
""", unsafe_allow_html=True)

# --- SETUP ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- HELPERS ---
def encode_image(file):
    return base64.b64encode(file.getvalue()).decode()

def crop_stamp(file):
    img = Image.open(file)
    w, h = img.size
    return img.crop((int(w*0.65), 0, w, int(h*0.35)))

def safe_parse(text):
    try:
        cleaned = text.replace("```json","").replace("```","").strip()
        return json.loads(cleaned)
    except:
        return None

def web_search(query):
    try:
        params = {
            "engine": "google",
            "q": query,
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "num": 5
        }
        results = GoogleSearch(params).get_dict()
        return [r.get("snippet","") for r in results.get("organic_results", [])]
    except:
        return []

# --- LAYOUT ---
left, right = st.columns([1,2])

with left:
    st.markdown('<div class="brand">', unsafe_allow_html=True)
    st.image("logo.png")
    st.markdown("### PostArk")
    st.markdown("Preserving history through postcards.")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.subheader("Upload Postcard")

    c1, c2 = st.columns(2)

    with c1:
        front_file = st.file_uploader("Front Image", type=["jpg","png"])

    with c2:
        back_file = st.file_uploader("Back Image", type=["jpg","png"])

    if front_file or back_file:
        p1, p2 = st.columns(2)
        if front_file:
            p1.image(front_file, use_container_width=True)
        if back_file:
            p2.image(back_file, use_container_width=True)

    run = st.button("🔍 Analyze Postcard")

# --- RESULTS ---
if run and front_file and back_file:

    progress = st.progress(0)
    status = st.empty()

    front_img = encode_image(front_file)
    back_img = encode_image(back_file)

    try:
        # EXTRACTION (RESTORED STRONG PROMPT)
        status.write("📖 Extracting...")
        progress.progress(20)

        vision_prompt = """
        Extract postcard data as JSON:

        {
          "sender": "",
          "receiver": "",
          "location_sent_from": "",
          "location_sent_to": "",
          "date": "",
          "full_transcription": "",
          "confidence": {
            "sender": 0.0,
            "receiver": 0.0,
            "location": 0.0,
            "date": 0.0
          }
        }
        """

        vision = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role":"user",
                "content":[
                    {"type":"input_text","text":vision_prompt},
                    {"type":"input_image","image_url":f"data:image/jpeg;base64,{front_img}"},
                    {"type":"input_image","image_url":f"data:image/jpeg;base64,{back_img}"}
                ]
            }]
        )

        raw_text = vision.output[0].content[0].text
        data = safe_parse(raw_text)

        if not data:
            data = {
                "sender": "Unknown",
                "receiver": "Unknown",
                "location_sent_from": "",
                "location_sent_to": "",
                "date": "",
                "full_transcription": raw_text,
                "confidence": {}
            }

        conf = data.get("confidence", {})

        # STAMP
        status.write("📮 Stamp...")
        progress.progress(40)

        stamp_image = crop_stamp(back_file)

        stamp_text = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role":"user",
                "content":[
                    {"type":"input_text","text":"Identify stamp details"},
                    {"type":"input_image","image_url":f"data:image/jpeg;base64,{back_img}"}
                ]
            }]
        ).output[0].content[0].text

        # TIMELINE (FIXED)
        status.write("📅 Timeline...")
        progress.progress(60)

        timeline = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
            Provide structured historical context:

            Date: {data.get('date')}
            Location: {data.get('location_sent_from')}

            Keep it grounded and specific.
            """
        ).output[0].content[0].text

        # STORY (FIXED)
        status.write("🧠 Story...")
        progress.progress(90)

        story = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
            Write a grounded historical narrative using ONLY:

            {data}
            {timeline}

            Do not invent facts.
            """
        ).output[0].content[0].text

        progress.progress(100)
        status.write("✅ Done")

    except Exception as e:
        st.error(str(e))
        st.stop()

    # --- OUTPUT ---
    st.markdown('<div class="results">', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Overview","Stamp","Timeline","Story"])

    # OVERVIEW (FIXED)
    with tab1:
        cols = st.columns(4)

        def card(label, value, c):
            return f"""
            <div class='info-card'>
                <div class='label'>{label}</div>
                <div class='value'>{value}</div>
                <div class='conf'>confidence: {round(c,2)}</div>
            </div>
            """

        cols[0].markdown(card("Sender", data.get("sender","—"), conf.get("sender",0)), unsafe_allow_html=True)
        cols[1].markdown(card("Receiver", data.get("receiver","—"), conf.get("receiver",0)), unsafe_allow_html=True)
        cols[2].markdown(card("From", data.get("location_sent_from","—"), conf.get("location",0)), unsafe_allow_html=True)
        cols[3].markdown(card("Date", data.get("date","—"), conf.get("date",0)), unsafe_allow_html=True)

        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### Message")
        st.write(data.get("full_transcription",""))
        st.markdown("</div>", unsafe_allow_html=True)

    # STAMP
    with tab2:
        col1, col2 = st.columns([1,2])
        col1.image(stamp_image, width=150)
        col2.markdown(f"<div class='card'>{stamp_text}</div>", unsafe_allow_html=True)

    # TIMELINE
    with tab3:
        st.markdown(f"<div class='card'>{timeline}</div>", unsafe_allow_html=True)

    # STORY
    with tab4:
        st.markdown(f"<div class='card story'>{story}</div>", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)