import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
import json
from serpapi import GoogleSearch
from PIL import Image
import time

# --- CONFIG ---
st.set_page_config(page_title="PostArk", page_icon="📬", layout="wide")

# --- STYLE ---
st.markdown("""
<style>

/* Left logo panel */
.logo-section {
    text-align: center;
    padding-top: 40px;
}

/* Cards */
.card {
    padding: 20px;
    border-radius: 12px;
    background: #f8f8f8;
    border: 1px solid #e5e5e5;
    margin-bottom: 15px;
}

/* Labels */
.label { font-size: 12px; color: #777; }
.value { font-size: 18px; font-weight: 600; }

/* Story */
.story {
    font-size: 18px;
    line-height: 1.9;
    padding: 28px;
    background: #f4f1ea;
    border-radius: 12px;
    border: 1px solid #ddd;
    color: #111;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-size: 18px !important;
    padding: 12px 22px !important;
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
        return json.loads(text.replace("```json","").replace("```","").strip())
    except:
        return {}

def web_search(query):
    params = {
        "engine": "google",
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": 3
    }
    results = GoogleSearch(params).get_dict()
    return [r.get("snippet","") for r in results.get("organic_results", [])]

# --- LAYOUT ---
left_col, right_col = st.columns([1, 4])

# --- LEFT: LOGO ---
with left_col:
    st.markdown('<div class="logo-section">', unsafe_allow_html=True)
    st.image("logo.png", width=180)
    st.markdown("## PostArk")
    st.caption("Preserving history, one postcard at a time")
    st.markdown('</div>', unsafe_allow_html=True)

# --- RIGHT: APP ---
with right_col:

    st.subheader("Upload Postcard")

    col1, col2 = st.columns(2)

    with col1:
        front_file = st.file_uploader("Front Image", type=["jpg","png"])

    with col2:
        back_file = st.file_uploader("Back Image", type=["jpg","png"])

    # --- PREVIEW ---
    if front_file or back_file:
        st.markdown("### Preview")

        col1, col2 = st.columns(2)

        with col1:
            if front_file:
                st.image(front_file, use_container_width=True)

        with col2:
            if back_file:
                st.image(back_file, use_container_width=True)

    # --- ANALYZE ---
    if st.button("🔍 Analyze Postcard") and front_file and back_file:

        progress = st.progress(0)
        status = st.empty()

        front_img = encode_image(front_file)
        back_img = encode_image(back_file)

        try:
            # STEP 1
            status.write("📖 Extracting postcard details...")
            progress.progress(20)

            vision = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract postcard data as JSON"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                    ]
                }]
            )

            raw_text = vision.output[0].content[0].text
            data = safe_parse(raw_text)

            if not data:
                st.error("Failed to parse postcard data.")
                st.text(raw_text)
                st.stop()

            # STEP 2
            status.write("📮 Analyzing stamp...")
            progress.progress(40)

            stamp_image = crop_stamp(back_file)

            # STEP 3
            status.write("🌐 Running research...")
            progress.progress(65)

            research_results = {}
            for person in [data.get("sender"), data.get("receiver")]:
                if person:
                    research_results[person] = web_search(person)

            # STEP 4
            status.write("🧠 Writing story...")
            progress.progress(85)

            narrative = client.responses.create(
                model="gpt-4.1-mini",
                input=f"""
                Write a historically grounded narrative.
                Do not invent facts.

                Data:
                {data}
                """
            )

            story = narrative.output[0].content[0].text

            progress.progress(100)
            status.write("✅ Complete")

            time.sleep(0.3)

        except Exception as e:
            st.error(f"Error during analysis: {e}")
            st.stop()

        st.divider()

        # --- TABS ---
        tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Stamp", "Story", "Analysis"])

        # OVERVIEW
        with tab1:
            cols = st.columns(4)

            def block(label, value):
                return f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"

            cols[0].markdown(block("Sender", data.get("sender","—")), unsafe_allow_html=True)
            cols[1].markdown(block("Receiver", data.get("receiver","—")), unsafe_allow_html=True)
            cols[2].markdown(block("From", data.get("location_sent_from","—")), unsafe_allow_html=True)
            cols[3].markdown(block("Date", data.get("date","—")), unsafe_allow_html=True)

            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("### Message")
            st.write(data.get("full_transcription",""))
            st.markdown("</div>", unsafe_allow_html=True)

        # STAMP
        with tab2:
            col1, col2 = st.columns([1,2])
            with col1:
                st.image(stamp_image, width=200)
            with col2:
                st.markdown("<div class='card'>Stamp identified from postcard.</div>", unsafe_allow_html=True)

        # STORY
        with tab3:
            st.markdown(f"<div class='story'>{story}</div>", unsafe_allow_html=True)

        # ANALYSIS
        with tab4:
            for person, snippets in research_results.items():
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown(f"**{person}**")
                for s in snippets:
                    st.write(f"- {s}")
                st.markdown("</div>", unsafe_allow_html=True)