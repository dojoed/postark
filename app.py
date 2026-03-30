from flask import Flask, request, render_template, send_file, redirect, url_for
from openai import OpenAI
import base64
import os
import sqlite3
import uuid
from dotenv import load_dotenv
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# --- SETUP ---
load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB = "artifacts.db"
UPLOAD_FOLDER = "static/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DB INIT ---
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            overview TEXT,
            analysis TEXT,
            story TEXT,
            timeline TEXT,
            front_path TEXT,
            back_path TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# --- HELPERS ---
def save_image(file):
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    return path


def encode_image_from_path(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def parse_sections(text):
    sections = {"overview": "", "analysis": "", "story": "", "timeline": ""}
    current = None

    for line in text.split("\n"):
        l = line.lower()

        if "overview" in l:
            current = "overview"
            continue
        elif "analysis" in l:
            current = "analysis"
            continue
        elif "story" in l:
            current = "story"
            continue
        elif "timeline" in l:
            current = "timeline"
            continue

        if current:
            sections[current] += line + "\n"

    return sections


def save_artifact(data, front_path, back_path):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        INSERT INTO artifacts (overview, analysis, story, timeline, front_path, back_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["overview"],
        data["analysis"],
        data["story"],
        data["timeline"],
        front_path,
        back_path
    ))

    artifact_id = c.lastrowid
    conn.commit()
    conn.close()

    return artifact_id


def get_artifact(artifact_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "overview": row[1],
        "analysis": row[2],
        "story": row[3],
        "timeline": row[4],
        "front_path": row[5],
        "back_path": row[6]
    }


# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            front = request.files.get("front")
            back = request.files.get("back")

            if not front or not back:
                return render_template("index.html", result={"error": "Upload both images."})

            # ✅ SAVE IMAGES PERMANENTLY
            front_path = save_image(front)
            back_path = save_image(back)

            front_img = encode_image_from_path(front_path)
            back_img = encode_image_from_path(back_path)

            prompt = """
Analyze this postcard and return:

OVERVIEW:
Short summary

ANALYSIS:
Sender, receiver, date, location

STORY:
Narrative

TIMELINE:
Bullet points
"""

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{front_img}"},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{back_img}"}
                    ]
                }]
            )

            raw = response.output[0].content[0].text
            parsed = parse_sections(raw)

            artifact_id = save_artifact(parsed, front_path, back_path)

            return redirect(url_for("artifact", artifact_id=artifact_id))

        except Exception as e:
            return render_template("index.html", result={"error": str(e)})

    return render_template("index.html", result=None)


@app.route("/artifact/<int:artifact_id>")
def artifact(artifact_id):
    data = get_artifact(artifact_id)

    if not data:
        return "Artifact not found", 404

    return render_template(
        "index.html",
        result=data,
        front_path="/" + data["front_path"],
        back_path="/" + data["back_path"],
        artifact_id=artifact_id
    )


# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)