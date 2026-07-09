from flask import Flask, request, jsonify, render_template_string
from extractor import run_extraction
import os
import uuid
import fitz  # PyMuPDF — also used here to genuinely validate PDF structure

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE_MB = 10
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

# Real PDF file signature (magic bytes). Every valid PDF starts with this,
# regardless of what the filename says. A renamed .exe or .jpg will NOT
# have these bytes, so checking this catches spoofed extensions.
PDF_MAGIC_BYTES = b"%PDF-"


def has_valid_pdf_signature(filepath):
    """Check the actual file content starts with the PDF magic bytes."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(5)
        return header == PDF_MAGIC_BYTES
    except Exception:
        return False


def is_pdf_structurally_valid(filepath):
    """
    Beyond the magic bytes, confirm PyMuPDF can actually open and parse
    the file as a PDF document (catches corrupted or truncated files that
    happen to still start with the right header).
    """
    try:
        doc = fitz.open(filepath)
        page_count = doc.page_count  # forces PyMuPDF to actually parse structure
        doc.close()
        return page_count > 0
    except Exception:
        return False

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

    # --- Real content validation, not just filename/extension ---
    # A file can be named "certificate.pdf" and still not actually be a PDF
    # (renamed image, executable, corrupted upload, etc). Check both:
    # 1) the file's magic bytes match the real PDF signature
    # 2) PyMuPDF can actually parse it as a structurally valid PDF
    if not has_valid_pdf_signature(filepath):
        os.remove(filepath)
        return jsonify({
            "error": "File does not have a valid PDF signature. "
                     "The extension says .pdf but the file content is not actually a PDF."
        }), 400

    if not is_pdf_structurally_valid(filepath):
        os.remove(filepath)
        return jsonify({
            "error": "File has a PDF header but could not be parsed as a valid PDF "
                     "(possibly corrupted or truncated)."
        }), 400

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