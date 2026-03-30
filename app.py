from flask import Flask, request, render_template, send_file
from openai import OpenAI
import base64
import os
from dotenv import load_dotenv
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# --- SETUP ---
load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- HELPERS ---
def encode_image(file, filename):
    data = base64.b64encode(file.read()).decode("utf-8")
    path = f"/tmp/{filename}"
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
    return data, path


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


def generate_pdf(data, front_path, back_path):
    file_path = "/tmp/artifact.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("<b>PostArk Artifact Report</b>", styles["Title"]))
    content.append(Spacer(1, 12))

    # Images
    content.append(Paragraph("<b>Postcard Images</b>", styles["Heading2"]))
    content.append(Spacer(1, 8))

    if os.path.exists(front_path):
        content.append(Image(front_path, width=250, height=150))
        content.append(Spacer(1, 8))

    if os.path.exists(back_path):
        content.append(Image(back_path, width=250, height=150))
        content.append(Spacer(1, 12))

    # Sections
    for key, title in [
        ("overview", "Overview"),
        ("analysis", "Detailed Analysis"),
        ("story", "Reconstructed Story"),
        ("timeline", "Timeline"),
    ]:
        content.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        content.append(Spacer(1, 6))
        content.append(Paragraph(data.get(key, ""), styles["BodyText"]))
        content.append(Spacer(1, 10))

    # Link back
    content.append(Paragraph("<b>View Online:</b> https://your-app-name.onrender.com", styles["Normal"]))

    doc.build(content)
    return file_path


# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    front_path = None
    back_path = None

    if request.method == "POST":
        try:
            front = request.files.get("front")
            back = request.files.get("back")

            if not front or not back:
                return render_template("index.html", result={"error": "Upload both images."})

            front_img, front_path = encode_image(front, "front.jpg")
            back_img, back_path = encode_image(back, "back.jpg")

            prompt = """
You are an expert historical archivist analyzing a vintage postcard.

Return sections:

OVERVIEW:
Short summary

ANALYSIS:
Sender, receiver, date, location, message summary

STORY:
Narrative

TIMELINE:
Bullet timeline
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

            result = parsed

        except Exception as e:
            result = {"error": str(e)}

    return render_template("index.html", result=result, front_path=front_path, back_path=back_path)


@app.route("/download", methods=["POST"])
def download():
    data = {
        "overview": request.form.get("overview"),
        "analysis": request.form.get("analysis"),
        "story": request.form.get("story"),
        "timeline": request.form.get("timeline"),
    }

    front_path = request.form.get("front_path")
    back_path = request.form.get("back_path")

    pdf_path = generate_pdf(data, front_path, back_path)
    return send_file(pdf_path, as_attachment=True)


# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)