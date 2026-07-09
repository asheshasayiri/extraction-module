import fitz
import pytesseract
from PIL import Image
import io
import re


# ---------------------------------------------------------------
# STEP 1: Extract raw text from PDF
# First tries embedded text (fast, for digital PDFs)
# Falls back to OCR (for scanned PDFs like your transcripts)
# ---------------------------------------------------------------

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    
    # Try embedded text first
    embedded = "".join(page.get_text() for page in doc).strip()
    if len(embedded) >= 50:
        return embedded
    
    # Scanned PDF — use Tesseract OCR
    full_text = ""
    doc = fitz.open(pdf_path)
    for page in doc:
        # zoom=3 gives ~216 DPI — good balance of speed vs accuracy
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        full_text += pytesseract.image_to_string(img, lang="eng") + "\n"
    
    return full_text


# ---------------------------------------------------------------
# STEP 2: Extract each field using regex
#
# re.search() scans the whole text for the first match
# re.IGNORECASE means CGPA and cgpa both match
# (.+?) is a "lazy capture" — grabs minimum needed
# [^\n]+ means "everything until end of line"
# \s* means "zero or more spaces" (handles spacing inconsistencies)
# ---------------------------------------------------------------

def extract_fields(text):

    def find(pattern, default=None):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else default

    # ---- INSTITUTION ----
    # Always the first non-empty line
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    institution = lines[0] if lines else None
    
    # Clean OCR typos: WAKANGAL → WARANGAL
    if institution:
        institution = institution.replace("WAKANGAL", "WARANGAL")

    # ---- NAME ----
    # Pattern 1: "Seth Ranjan Chodagam Degree : B.Tech."
    name = find(r"^([A-Z][a-zA-Z\s]+?)\s+Degree\s*:")
    
    # Pattern 2: "Name Prateek Saxena Course" or "Name : Prateek Saxena Course"
    if not name:
        name = find(r"Name\s*[+:_]?\s*([A-Z][a-zA-Z\s]+?)\s+Course")
    
    # Pattern 3: "Name _ : Katragadda Pragna Course"
    if not name:
        name = find(r"Name\s*[_\s]*:\s*([A-Z][a-zA-Z\s]+?)\s+Course")

    # Clean trailing noise like "Course" appearing in the name
    if name:
        name = re.sub(r"\s*(Course|Degree|Division).*$", "", name, flags=re.IGNORECASE).strip()

    # ---- ROLL NUMBER ----
    # Handles: "Roll No. : 21ECBOFO6", "Roll No. : 184147", "Roll No. : UG104137"
    roll_no = find(r"Roll\s*No[.\s]*:?\s*([A-Z0-9]+)")

    # ---- COURSE / DEGREE ----
    # Handles: "Course B. TECH." and "Course : B. TECH."
    # Stops before "Division" which follows on same line
    course = find(r"Course\s*:?\s*(B\.?\s*TECH\.?|M\.?\s*TECH\.?|B\.?\s*E\.?|MBA|MCA|BCA|BSC|MSC)")
    
    # Fallback: "Degree : B.Tech."
    if not course:
        course = find(r"Degree\s*:\s*(B\.?\s*Tech\.?|M\.?\s*Tech\.?)")

    # ---- SPECIALIZATION ----
    # Handles both "Specialization:" and "Specialization :"
    specialization = find(r"Specialization\s*:\s*([A-Z][^\n]+?)(?:\s*$|\s+[A-Z]{2,}\s+SEMESTER)")
    
    if not specialization:
        specialization = find(r"Specialization\s*:\s*([^\n]+)")
    
    # Clean trailing noise
    if specialization:
        specialization = re.sub(r"\s*(Roll|No\.|Course|Division).*$", "", specialization, flags=re.IGNORECASE).strip()

    # ---- DIVISION ----
    # Handles: "Division: First Division Only." and "Division : Second Division only"
    division = find(r"Division\s*:\s*((?:First|Second|Pass)\s+Division[^\n.]*)")
    
    if division:
        division = division.replace("Only.", "").replace("only", "").replace("Only", "").strip()

    # ---- CGPA ----
    # CRITICAL: use findall() to get ALL matches, then take the LAST one
    # because transcripts show CGPA after every semester
    # The FINAL value = graduation CGPA
    cgpa_matches = re.findall(
        r"CGPA\s*[:\s]\s*(\d+\.\d+)",
        text,
        re.IGNORECASE
    )
    cgpa = cgpa_matches[-1] if cgpa_matches else None

    # ---- GRADUATION YEAR ----
    # Find all month+year combinations, take the last one
    year_matches = re.findall(
        r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
        r"[\s\-]+(\d{4})",
        text,
        re.IGNORECASE
    )
    graduation_year = year_matches[-1] if year_matches else None

    # ---- EMAIL ----
    # Rarely appears in transcripts, but check anyway
    email = find(r"[\w.\-]+@[\w.\-]+\.[a-z]{2,}")

    return {
        "name": name,
        "email": email,
        "roll_no": roll_no,
        "course": course,
        "specialization": specialization,
        "division": division,
        "cgpa": cgpa,
        "institution": institution,
        "graduation_year": graduation_year,
    }


# ---------------------------------------------------------------
# STEP 3: Validate and score confidence
# Counts how many fields were successfully extracted
# Returns a percentage — useful for "requires_review" decision
# ---------------------------------------------------------------

def validate_fields(data):
    # Email is optional in transcripts, don't count it
    required_fields = ["name", "roll_no", "course", "specialization", 
                       "division", "cgpa", "institution", "graduation_year"]
    
    filled = sum(1 for f in required_fields if data.get(f))
    return round((filled / len(required_fields)) * 100, 2)


# ---------------------------------------------------------------
# STEP 4: Main pipeline — called by app.py
# ---------------------------------------------------------------

def run_extraction(pdf_path):
    text = extract_text(pdf_path)
    data = extract_fields(text)
    
    confidence = validate_fields(data)
    data["confidence_score"] = f"{confidence}%"
    
    # Always true — issuer must review before anything goes on-chain
    data["requires_review"] = True
    
    return data