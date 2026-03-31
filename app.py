import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
import json
from serpapi import GoogleSearch
from PIL import Image

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Postcard History Agent",
    page_icon="📬",
    layout="wide"
)

# --- CLEAN SPACING ---
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem;
}
h1 {
    margin-top: 0rem;
}
.story {
    font-size: 16px;
    line-height: 1.6;
    background: #0f172a;
    padding: 18px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# --- SETUP ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- HELPERS ---
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode("utf-8")


def crop_stamp(uploaded_file):
    image = Image.open(uploaded_file)
    width, height = image.size

    crop_box = (
        int(width * 0.65),
        0,
        width,
        int(height * 0.35)
    )

    return image.crop(crop_box)


def web_search(query):
    params = {
        "engine": "google",
        "q": query,
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "num": 5
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    snippets = []
    if "organic_results" in results:
        for r in results["organic_results"]:
            snippets.append(r.get("snippet", ""))

    return "\n".join(snippets)


# --- HEADER ---
st.title("📬 Postcard History Agent")
st.caption("Uncover the story behind historical postcards — people, places, and stamps")

st.divider()

# --- UPLOAD ---
st.subheader("Upload Postcard")

col1, col2 = st.columns(2)

with col1:
    front_file = st.file_uploader("Front Image", type=["jpg", "png"])

with col2:
    back_file = st.file_uploader("Back Image", type=["jpg", "png"])

# --- DISPLAY IMAGES ---
if front_file or back_file:
    st.divider()

    img_col1, img_col2 = st.columns(2)

    with img_col1:
        if front_file:
            st.image(front_file, caption="Front", use_container_width=True)

    with img_col2:
        if back_file:
            st.image(back_file, caption="Back", use_container_width=True)


# --- MAIN ANALYSIS ---
if st.button("🔍 Analyze Postcard") and front_file and back_file:

    with st.status("Analyzing postcard...", expanded=True):

        front_img = encode_image(front_file)
        back_img = encode_image(back_file)

        # --- STEP 1: VISION ---
        st.write("🔍 Extracting postcard details...")

        vision_prompt = """
        Extract postcard data as JSON:
        {
          "sender": "",
          "receiver": "",
          "location_sent_from": "",
          "location_sent_to": "",
          "date": "",
          "full_transcription": "",
          "observations": ""
        }
        """

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": vision_prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                ]
            }]
        )

        structured = response.output[0].content[0].text
        structured = structured.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(structured)
        except:
            st.error("Failed to parse extracted data")
            st.text(structured)
            st.stop()

        # --- STEP 2: STAMP ---
        st.write("📮 Analyzing stamp...")

        stamp_prompt = """
        Analyze stamp and return JSON:
        {
          "country": "",
          "denomination": "",
          "year_or_era": "",
          "stamp_description": "",
          "postmark_details": ""
        }
        """

        stamp_response = client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": stamp_prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                ]
            }]
        )

        stamp_raw = stamp_response.output[0].content[0].text
        stamp_raw = stamp_raw.replace("```json", "").replace("```", "").strip()

        try:
            stamp_data = json.loads(stamp_raw)
        except:
            stamp_data = {"error": "Could not parse stamp data", "raw": stamp_raw}

        stamp_image = crop_stamp(back_file)

        # --- STEP 3: RESEARCH ---
        st.write("🌐 Running research...")

        research_results = {}

        for key in ["sender", "receiver"]:
            val = data.get(key)
            if val:
                query = f"{val} genealogy history"
                st.write(f"🧠 Searching: {query}")
                research_results[val] = web_search(query)

        # --- STEP 4: NARRATIVE ---
        st.write("📖 Generating narrative...")

        narrative = client.responses.create(
            model="gpt-4.1-mini",
            input=f"Explain this postcard with context: {data}"
        )

        narrative_text = narrative.output[0].content[0].text

    # --- RESULTS ---
    st.divider()

    tab1, tab2, tab3 = st.tabs(["🧾 Overview", "📮 Stamp", "📖 Story"])

    # OVERVIEW
    with tab1:
        st.subheader("Postcard Details")
        st.json(data)

    # STAMP TAB (IMAGE LEFT, DETAILS RIGHT)
    with tab2:
        st.subheader("📮 Stamp Analysis")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(stamp_image, caption="Detected Stamp", width=180)

        with col2:
            st.markdown("### Details")
            st.markdown(f"**Country:** {stamp_data.get('country', 'Unknown')}")
            st.markdown(f"**Denomination:** {stamp_data.get('denomination', 'Unknown')}")
            st.markdown(f"**Era:** {stamp_data.get('year_or_era', 'Unknown')}")
            st.markdown(f"**Description:** {stamp_data.get('stamp_description', 'N/A')}")

            if stamp_data.get("postmark_details"):
                st.markdown(f"**Postmark:** {stamp_data.get('postmark_details')}")

    # STORY
    with tab3:
        st.subheader("Historical Narrative")
        st.markdown(f"<div class='story'>{narrative_text}</div>", unsafe_allow_html=True)