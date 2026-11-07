"""
File parsing: PDF, DOCX, TXT → plain text.
Hardened against disguised uploads, path traversal, zip bombs, and slowloris parsing.
"""
import io
import os
import re
import zipfile
import structlog
from fastapi import HTTPException

log = structlog.get_logger()

# Magic bytes for allowed types
_MAGIC = {
    b"%PDF":           "pdf",
    b"PK\x03\x04":    "docx",   # ZIP-based (DOCX)
    b"\xef\xbb\xbf":  "txt",    # UTF-8 BOM
}

MAX_DECOMPRESSED_DOCX_BYTES = 50 * 1024 * 1024  # 50 MB limit (Zip-bomb defense)
MAX_COMPRESSION_RATIO = 100                      # 100:1 ratio limit


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and special character exploits.
    Path components are stripped, keeping only a safe basename.
    """
    basename = os.path.basename(filename).strip()
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", basename)
    return clean[:120] if clean else "unnamed_document"


def detect_file_type(content: bytes, filename: str) -> str:
    """
    Detect file type from magic bytes first, extension as fallback.
    Prevents disguised uploads (e.g. .exe or .sh renamed to .pdf).
    """
    for magic, ftype in _MAGIC.items():
        if content.startswith(magic):
            return ftype

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"pdf", "docx", "txt"}
    if ext in allowed:
        # Plain text has no magic bytes
        if ext == "txt":
            return "txt"

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type. Allowed: pdf, docx, txt"
    )


def _check_docx_zip_bomb(content: bytes):
    """Inspect DOCX zip archive header for decompression bombs before extracting."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            total_uncompressed = 0
            total_compressed = len(content)

            for info in zf.infolist():
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_DECOMPRESSED_DOCX_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail="File rejected: Decompressed size exceeds safety threshold (possible zip bomb)"
                    )

            if total_compressed > 0 and (total_uncompressed / total_compressed) > MAX_COMPRESSION_RATIO:
                raise HTTPException(
                    status_code=400,
                    detail="File rejected: Unusually high compression ratio detected (possible zip bomb)"
                )
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Invalid or corrupt DOCX archive")


def parse_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        if len(reader.pages) > 200:
            raise HTTPException(status_code=400, detail="Document exceeds maximum 200-page limit")

        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(text)
        return "\n\n".join(pages)
    except HTTPException:
        raise
    except Exception as e:
        log.error("pdf_parse_error", error=str(e))
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")


def parse_docx(content: bytes) -> str:
    """Extract text from DOCX bytes with zip-bomb protection."""
    _check_docx_zip_bomb(content)
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except HTTPException:
        raise
    except Exception as e:
        log.error("docx_parse_error", error=str(e))
        raise HTTPException(status_code=422, detail=f"Failed to parse DOCX: {e}")


def parse_txt(content: bytes) -> str:
    """Decode plain text safely."""
    try:
        return content.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to decode text: {e}")


def parse_document(content: bytes, filename: str) -> tuple[str, str]:
    """
    Validates, sanitizes, and extracts text.
    Returns (file_type, extracted_text).
    """
    safe_name = sanitize_filename(filename)
    file_type = detect_file_type(content, safe_name)

    if file_type == "pdf":
        text = parse_pdf(content)
    elif file_type == "docx":
        text = parse_docx(content)
    else:
        text = parse_txt(content)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Document appears empty after parsing")

    log.info("document_parsed", filename=safe_name, file_type=file_type, chars=len(text))
    return file_type, text
