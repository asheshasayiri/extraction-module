import platform
import shutil
import fitz
import pytesseract
from PIL import Image

# Cross-platform tesseract path handling.
# Original code hardcoded a Windows-only path unconditionally, which crashes
# immediately on Linux/Mac (e.g. Render, Vercel, teammates' machines).
if platform.system() == "Windows":
    windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if shutil.which("tesseract") is None:
        pytesseract.pytesseract.tesseract_cmd = windows_path
# On Linux/Mac, pytesseract will find `tesseract` on PATH automatically
# as long as it's installed (e.g. `apt install tesseract-ocr` / `brew install tesseract`).


def extract_text_with_ocr(pdf_path):

    doc = fitz.open(pdf_path)
    text = ""

    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        page_text = pytesseract.image_to_string(img)
        text += page_text

    return text.strip()
