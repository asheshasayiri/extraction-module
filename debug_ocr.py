import fitz
import pytesseract
from PIL import Image
import io
import sys

def print_ocr_text(pdf_path):
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        print(f"\n=== PAGE {i+1} ===")
        
        # Render page as high-res image (zoom=3 = ~216 DPI, clearer text)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        img_bytes = pix.tobytes("png")
        
        # Convert to PIL Image for Tesseract
        img = Image.open(io.BytesIO(img_bytes))
        
        # Run OCR
        text = pytesseract.image_to_string(img)
        print(text)

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "transcript.pdf"
    print_ocr_text(path)