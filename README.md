# VeriBlock — Certificate Field Extraction Module (Offline, LLM-Free)

Extracts student details (name, roll number, degree, CGPA, etc.) from an
uploaded certificate/transcript PDF and returns structured JSON — entirely
locally, with no external API dependency.

**This is a pre-fill helper only.** It never writes to IPFS or the
blockchain. The issuer always reviews and manually confirms every field
before anything goes on-chain (`requires_review: true` in every response).

---

## Why offline instead of an LLM API?

An earlier version of this module called an LLM (OpenAI, then Claude) to
extract fields. That version worked, but every request depended on a
third-party vendor being reachable and funded — it failed whenever the
API key ran out of credits or the provider had an outage.

This version removes that dependency entirely:

- **PyMuPDF (`fitz`)** reads embedded text directly from text-based PDFs
- **Tesseract OCR** kicks in as a fallback for scanned/image-based PDFs
- **Regex** parses the extracted text into structured fields

No API key, no internet connection required to run extraction, no vendor
billing risk. Note: this is a *vendor-dependency* fix, not a change to the
project's blockchain decentralization — verification trust still comes
from the smart contract + IPFS anchor, not from how the issue form gets
pre-filled.

**Trade-off to be aware of:** the regex patterns are tuned to this
transcript's specific layout (see "Known limitations" below). The LLM
version generalized across formats more easily; this version is faster
and dependency-free but less flexible to new certificate templates.

---

## How it works

```
Upload PDF
    |
    v
Try embedded text extraction (PyMuPDF)
    |
    ├── Enough text found (>= 50 chars) ──> use it directly
    |
    └── Too little text (scanned image) ──> run Tesseract OCR ──> use OCR text
    |
    v
Regex field extraction
(name, roll_no, course, specialization, division, cgpa, institution, graduation_year)
    |
    v
Confidence scoring (utils.py) + requires_review: true
    |
    v
Return JSON
```

---

## File validation (security)

Earlier versions only checked that the filename ended in `.pdf` — trivially
spoofable by renaming any file. This version validates the actual file
content before processing:

1. **Magic-byte check** — confirms the file's first bytes are the real PDF
   signature (`%PDF-`), regardless of what the filename claims.
2. **Structural check** — attempts to actually open the file with PyMuPDF
   and confirms it has real, parseable pages. Catches corrupted/truncated
   files that fake the header but aren't valid PDFs.

A file failing either check is deleted immediately and rejected with a
`400` error before it ever reaches the OCR/extraction pipeline.

**Still open (not fixed yet, noted honestly):**
- No authentication on `/extract` — acceptable for a trusted-user demo,
  not for a public-facing production endpoint
- No rate limiting — a single user could spam the endpoint with large
  scanned PDFs and consume CPU (OCR is not cheap)

---

## API

### `POST /extract`

**Request:** `multipart/form-data`, field name `file`, PDF only.

**Success response:**
```json
{
  "name": "Seth Ranjan Chodagam",
  "email": null,
  "roll_no": "21ECB0F06",
  "course": "B.Tech.",
  "specialization": "ELECTRONICS AND COMMUNICATION ENGINEERING",
  "division": "Second Division",
  "cgpa": "8.42",
  "institution": "NIT WARANGAL",
  "graduation_year": "2025",
  "confidence_score": "100.0%",
  "requires_review": true
}
```

**Error responses:**
| Status | Meaning |
|---|---|
| 400 | No file / empty filename / wrong extension |
| 400 | File extension is `.pdf` but content fails the PDF magic-byte check |
| 400 | File has a valid PDF header but PyMuPDF cannot parse its structure |
| 500 | Unexpected server-side extraction failure |

---

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

Requires Tesseract OCR installed on the system (`apt install tesseract-ocr`
on Linux, or see Dockerfile for the exact package). No `.env` file or API
key needed — this is the whole point of the offline version.

Visit `http://localhost:8080` for a minimal built-in test UI, or hit
`/extract` directly with Postman/curl.

## Deployment

Deployed on Railway using the included `Dockerfile` (installs
`tesseract-ocr` + `libtesseract-dev` at build time) and `Procfile`
(`gunicorn app:app`). `nixpacks.toml` is an alternative build config if
Railway's Nixpacks builder is used instead of the Dockerfile.

---

## Known limitations

- Regex patterns are tuned to this specific transcript layout
  (`Degree :`, `Roll No. :`, etc.). A differently formatted certificate
  from another institution will likely return `null` for several fields.
  Extending to new formats requires adding new regex patterns per template.
- Institution name is assumed to be the first non-empty line of the
  document — fragile if a scanned copy has a logo/header line before the
  actual institution name.
- Confidence score is a single global percentage (fields present ÷ total
  fields), not per-field — a reviewer can't tell *which* specific field to
  double-check, only that something may be missing overall.
