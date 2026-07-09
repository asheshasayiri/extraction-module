from flask import Flask, request, jsonify, render_template_string
from extractor import run_extraction
import os
import uuid

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE_MB = 10
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

# Simple demo UI — just for testing and demo purposes
@app.route("/")
def home():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Certificate Extraction API</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
        h1 { font-size: 22px; }
        p { color: #555; font-size: 14px; }
        input[type=file] { margin: 16px 0; display: block; }
        button { background: #5c4ab7; color: white; border: none; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; }
        button:disabled { opacity: 0.5; }
        pre { background: #f5f5f5; padding: 16px; border-radius: 8px; font-size: 13px; overflow-x: auto; white-space: pre-wrap; }
        .status { color: #888; font-size: 13px; margin: 8px 0; }
        .error { color: #c0392b; }
    </style>
</head>
<body>
    <h1>Certificate Extraction</h1>
    <p>Upload a certificate or transcript PDF. The system will extract student details locally — no internet or AI API used.</p>

    <input type="file" id="fileInput" accept="application/pdf" />
    <button id="uploadBtn" onclick="uploadFile()">Extract fields</button>
    <p class="status" id="status"></p>
    <pre id="result" style="display:none"></pre>

    <script>
        async function uploadFile() {
            const fileInput = document.getElementById('fileInput');
            const status = document.getElementById('status');
            const result = document.getElementById('result');
            const btn = document.getElementById('uploadBtn');

            if (!fileInput.files[0]) {
                status.textContent = 'Please select a PDF file first.';
                return;
            }

            btn.disabled = true;
            status.textContent = 'Extracting... this may take 10-20 seconds for scanned PDFs.';
            result.style.display = 'none';

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            try {
                const response = await fetch('/extract', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                result.textContent = JSON.stringify(data, null, 2);
                result.style.display = 'block';
                status.textContent = 'Done.';
            } catch (err) {
                status.innerHTML = '<span class="error">Request failed: ' + err.message + '</span>';
            } finally {
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
    """)


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
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")