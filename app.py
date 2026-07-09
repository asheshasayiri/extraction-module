from flask import Flask, request, jsonify
from extractor import run_extraction
import os
import uuid

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE_MB = 10
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)


@app.route("/")
def home():
    return "AI Certificate Extraction API Running \U0001F680"


@app.route("/extract", methods=["POST"])
def extract():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Use form field name 'file'."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type '{ext}'. Only PDF is supported."}), 400

    # Unique filename per request so concurrent uploads never collide/overwrite each other
    filepath = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.pdf")
    file.save(filepath)

    try:
        result = run_extraction(filepath)
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
