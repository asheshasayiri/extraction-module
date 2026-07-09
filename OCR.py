import platform
import shutil
import fitz
import pytesseract
from PIL import Image
import io   # ✅ ADD THIS

# Cross-platform tesseract path handling
if platform.system() == "Windows":
    windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if shutil.which("tesseract") is None:
        pytesseract.pytesseract.tesseract_cmd = windows_path

def extract_text_via_ocr(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        full_text = ""

        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))  # now works

            text = pytesseract.image_to_string(img, lang="eng")
            full_text += text + "\n"

        return full_text

    except Exception as e:
        return f"OCR_ERROR: {str(e)}"