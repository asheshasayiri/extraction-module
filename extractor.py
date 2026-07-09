import fitz
import pytesseract
from PIL import Image
import io
import re
from utils import validate_fields


def extract_text_via_ocr(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        # zoom=3 = ~216 DPI, sharper image = better OCR accuracy
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        # image_to_string reads pixels and recognises characters locally
        text = pytesseract.image_to_string(img, lang="eng")
        full_text += text + "\n"
    return full_text


def extract_fields(text):

    def find(pattern, default=None):
        # re.search scans the whole text, returns first match
        # .group(1) gives the captured part inside the brackets
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else default

    # ---- INSTITUTION ----
    # Always the first non-empty line of the document
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    institution = lines[0] if lines else None
    # Fix common OCR typo: WAKANGAL → WARANGAL
    if institution:
        institution = institution.replace("WAKANGAL", "WARANGAL")

    # ---- NAME ----
    # Pattern 1: "Seth Ranjan Chodagam Degree : B.Tech."
    # (.+?) captures lazily — stops at first "Degree"
    name = find(r"^([A-Z][a-zA-Z\s]+?)\s+Degree\s*:", )

    # Pattern 2: "Name : Mittapalli Ravikumar Course : B.TECH."
    # Handles Name appearing mid-line with colon
    if not name:
        name = find(r"Name\s*[+:_]?\s*([A-Z][a-zA-Z\s]+?)\s+Course")

    # Pattern 3: "Name _ : Katragadda Pragna Course"
    if not name:
        name = find(r"Name\s*[_\s]*:\s*([A-Z][a-zA-Z\s]+?)\s+Course")

    # Fallback: scan first 6 lines for a mixed-case name line
    if not name:
        for line in lines[1:6]:
            if re.match(r"^[A-Z][a-z]", line):
                name = line.split("Degree")[0].split("Course")[0].strip()
                break

    # Clean any trailing noise
    if name:
        name = re.sub(
            r"\s*(Course|Degree|Division|Roll).*$", "",
            name, flags=re.IGNORECASE
        ).strip()

    # ---- ROLL NUMBER ----
    # Handles: "Roll No. : 21ECBOFO6", "Roll No. : 184147", "Roll No. : UG104137"
    # \w+ matches both letters and digits (alphanumeric roll numbers)
    roll_no = find(r"Roll\s*No[.\s]*:?\s*([A-Z0-9]+)")

    # ---- COURSE ----
    # KEY FIX: course appears mid-line in some files:
    # "Name : Ravikumar Course : B. TECH. Division: Second Division."
    # Old regex missed this. New regex finds "Course :" anywhere in text
    # then immediately grabs the degree abbreviation that follows.
    course = find(
        r"Course\s*:?\s*(B\.?\s*TECH\.?|M\.?\s*TECH\.?|B\.?\s*E\.?"
        r"|MBA|MCA|BCA|BSC|MSC|B\.?\s*Sc\.?|M\.?\s*Sc\.?)"
    )

    # Fallback: "Degree : B.Tech."
    if not course:
        course = find(
            r"Degree\s*:\s*(B\.?\s*Tech\.?|M\.?\s*Tech\.?|B\.?\s*E\.?)"
        )

    # Normalise: "B. TECH." → "B.Tech.", "M. TECH." → "M.Tech."
    if course:
        course = re.sub(r"B\.?\s*TECH\.?", "B.Tech.", course, flags=re.IGNORECASE)
        course = re.sub(r"M\.?\s*TECH\.?", "M.Tech.", course, flags=re.IGNORECASE)
        course = course.strip()

    # ---- SPECIALIZATION ----
    # Handles both "Specialization:" and "Specialization :"
    specialization = find(r"Specialization\s*:\s*([A-Z][^\n]+?)(?:\s*$|\n)")
    if not specialization:
        specialization = find(r"Specialization\s*:\s*([^\n]+)")
    # Clean trailing noise
    if specialization:
        specialization = re.sub(
            r"\s*(Roll|No\.|Course|Division).*$", "",
            specialization, flags=re.IGNORECASE
        ).strip()

    # ---- DIVISION ----
    # Handles: "Division: First Division Only." and "Division : Second Division only"
    division = find(
        r"Division\s*:\s*((?:First|Second|Pass)\s+Division[^\n.]*)"
    )
    # Clean trailing words like "Only", "only."
    if division:
        division = re.sub(
            r"\s*(Only|only)\.?$", "", division
        ).strip()

    # ---- CGPA ----
    # findall() gets EVERY CGPA value in the document
    # [-1] gives the LAST one = final graduation CGPA
    # (transcripts print CGPA after every semester)
    cgpa_matches = re.findall(
        r"CGPA\s*[:\s]\s*(\d+\.\d+)", text, re.IGNORECASE
    )
    cgpa = cgpa_matches[-1] if cgpa_matches else None

    # ---- GRADUATION YEAR ----
    # Find all "MONTH YEAR" patterns, take the last = final semester
    year_matches = re.findall(
        r"(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY"
        r"|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)"
        r"[\s\-]+(\d{4})",
        text, re.IGNORECASE
    )
    graduation_year = year_matches[-1] if year_matches else None

    # ---- EMAIL ----
    # Rarely in transcripts but check anyway
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


def run_extraction(pdf_path):
    # Fast path: try embedded text first (digital PDFs)
    doc = fitz.open(pdf_path)
    embedded_text = "".join(page.get_text() for page in doc).strip()

    if len(embedded_text) >= 50:
        text = embedded_text   # text-based PDF, no OCR needed
    else:
        text = extract_text_via_ocr(pdf_path)   # scanned PDF

    data = extract_fields(text)

    confidence = validate_fields(data)
    data["confidence_score"] = f"{confidence}%"
    data["requires_review"] = True  # issuer must always confirm before on-chain

    return data