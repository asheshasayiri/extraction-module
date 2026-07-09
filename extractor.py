import fitz
import pytesseract
from PIL import Image
import io
import re
from utils import validate_fields


# ---------------------------------------------------------------
# Step 1 — Render PDF pages as images, then run Tesseract OCR
# This replaces the Gemini API call entirely.
# fitz (PyMuPDF) renders each page as a pixel image.
# Tesseract then reads those pixels and returns raw text.
# All of this runs locally — no internet, no API key needed.
# ---------------------------------------------------------------

def extract_text_via_ocr(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""

    for page in doc:
        # zoom=3 means 3x the default resolution (~216 DPI)
        # Higher zoom = sharper image = better OCR accuracy
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        img_bytes = pix.tobytes("png")

        # Convert raw bytes into a PIL Image object
        # Tesseract only accepts PIL Images, not raw bytes
        img = Image.open(io.BytesIO(img_bytes))

        # image_to_string() is Tesseract's core function
        # It looks at the image pixel by pixel and recognises characters
        # lang="eng" tells it to expect English text
        text = pytesseract.image_to_string(img, lang="eng")
        full_text += text + "\n"

    return full_text


# ---------------------------------------------------------------
# Step 2 — Extract each field using regex
#
# What is regex?
# re.search(pattern, text) scans through text and finds
# the FIRST match of your pattern. If found, .group(1)
# gives you the captured part (what's inside the brackets).
#
# Key symbols used here:
#   .+?    = one or more of any character, lazy (stops at first match)
#   \d     = any digit (0-9)
#   \s*    = zero or more spaces/tabs
#   re.IGNORECASE = treat uppercase and lowercase as the same
# ---------------------------------------------------------------

def extract_fields(text):

    def find(pattern, default=None):
        # Helper: run the regex, return the captured group or default
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # .strip() removes any trailing spaces/newlines from the result
            return match.group(1).strip()
        return default

    # ---- Name ----
    # Pattern: find the first line of real text at the top
    # We look for text that appears BEFORE "Degree :"
    # In your transcript: "Seth Ranjan Chodagam Degree : B.Tech."
    # (.+?) captures everything up to but not including "Degree"
    name = find(r"^([A-Z][a-zA-Z\s]+?)\s+Degree\s*:", )

    # If that didn't work, try the second non-empty line
    # (institution is line 1, name is often line 2 or nearby)
    if not name:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # Skip the institution line (all caps) and find the first mixed-case line
        for line in lines[1:6]:
            if re.match(r"^[A-Z][a-z]", line):
                name = line.split("Degree")[0].strip()
                break

    # ---- Roll Number ----
    # Pattern: "Roll No. : 21ECBOFO6"
    # \w+ matches letters and digits (roll numbers are alphanumeric)
    roll_no = find(r"Roll\s*No[.\s]*:\s*(\w+)")

    # ---- Degree ----
    # Pattern: "Degree : B.Tech."
    # [^\n]+ captures everything until the end of the line
    degree = find(r"Degree\s*:\s*([^\n|]+?)\s+Division")

    # ---- Specialization ----
    # Pattern: "Specialization : ELECTRONICS AND COMMUNICATION ENGINEERING"
    specialization = find(r"Specialization\s*:\s*([^\n]+)")

    # ---- Division ----
    # Pattern: "Division : Second Division only"
    division = find(r"Division\s*:\s*([^\n|]+?)(?:\s+Roll|\s*$)")

    # ---- CGPA ----
    # IMPORTANT: We want the LAST CGPA in the document,
    # because transcripts show CGPA after every semester.
    # The final value is the graduation CGPA.
    # findall() returns ALL matches, [-1] gives us the last one.
    cgpa_matches = re.findall(r"CGPA\s*[:\s]\s*(\d+\.\d+)", text, re.IGNORECASE)
    cgpa = cgpa_matches[-1] if cgpa_matches else None

    # ---- Institution ----
    # Pattern: institution name is almost always the first non-empty line
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    institution = lines[0] if lines else None

    # ---- Graduation Year ----
    # Look for the last semester examination date mentioned
    # Pattern: "APRIL 2025" or "DECEMBER 2024" etc.
    year_matches = re.findall(
        r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})",
        text, re.IGNORECASE
    )
    graduation_year = year_matches[-1] if year_matches else None

    return {
        "name": name,
        "email": None,          # emails rarely appear in transcripts
        "roll_no": roll_no,
        "course": degree,
        "specialization": specialization,
        "division": division,
        "cgpa": cgpa,
        "institution": institution,
        "graduation_year": graduation_year,
    }


# ---------------------------------------------------------------
# Step 3 — Main pipeline
# Called by app.py exactly the same way as before.
# app.py does not need any changes.
# ---------------------------------------------------------------

def run_extraction(pdf_path):

    # First try: can PyMuPDF read embedded text? (fast path)
    doc = fitz.open(pdf_path)
    embedded_text = "".join(page.get_text() for page in doc).strip()

    if len(embedded_text) >= 50:
        # Text-based PDF — no OCR needed, use text directly
        text = embedded_text
    else:
        # Scanned PDF — run Tesseract OCR to get the text
        text = extract_text_via_ocr(pdf_path)

    # Extract fields from whatever text we got
    data = extract_fields(text)

    # Run validation (same utils.py as before — no changes there)
    confidence = validate_fields(data)
    data["confidence_score"] = f"{confidence}%"
    data["requires_review"] = True   # issuer must always confirm before going on-chain

    return data