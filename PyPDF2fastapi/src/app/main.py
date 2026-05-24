from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import tempfile
import subprocess
import shutil
import os

app = FastAPI(
    title="Selfhost PDF Compressor Tool - FastAPI",
    description=(
        "Selfhost PDF Compressor Tool (FastAPI). "
        "Provides lossless compression (pypdf) and optional lossy optimizations via Ghostscript "
        "with endpoints: /compress/lossless, /compress/optimized, /compress/little, /compress/max."
    ),
)


@app.get("/ping")
async def ping():
    return {"status": "ok", "project": "Selfhost PDF Compressor Tool - FastAPI"}


def _validate_pdf_upload(file: UploadFile):
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")


def _compress_lossless_bytes(input_bytes: bytes) -> bytes:
    input_buffer = BytesIO(input_bytes)
    reader = PdfReader(input_buffer)
    writer = PdfWriter()

    for page in reader.pages:
        try:
            page.compress_content_streams()
        except Exception:
            pass
        writer.add_page(page)

    output_buffer = BytesIO()
    writer.write(output_buffer)
    return output_buffer.getvalue()


def _run_ghostscript_bytes(input_bytes: bytes, pdfsetting: str) -> bytes:
    gs_path = shutil.which("gs")
    if not gs_path:
        raise RuntimeError("Ghostscript (gs) not available in container")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as inf:
        inf.write(input_bytes)
        inf.flush()
    out_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    try:
        cmd = [
            gs_path,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={pdfsetting}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={out_path}",
            inf.name,
        ]
        subprocess.run(cmd, check=True)
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(inf.name)
        except Exception:
            pass
        try:
            os.remove(out_path)
        except Exception:
            pass


def _calculate_savings_headers(original_size: int, compressed_size: int, method: str, filename: str, prefix: str) -> dict:
    saved_size = original_size - compressed_size
    savings_pct = round((saved_size / original_size) * 100, 2) if original_size > 0 else 0
    return {
        "Content-Disposition": f'attachment; filename="{prefix}_{filename}"',
        "X-Original-Size": str(original_size),
        "X-Compressed-Size": str(compressed_size),
        "X-Saved-Size": str(saved_size),
        "X-Savings-Percentage": f"{savings_pct}%",
        "X-Compression-Method": method,
    }


@app.post("/compress")
async def compress_pdf(file: UploadFile = File(...)):
    # alias to lossless for backward compatibility
    return await compress_lossless(file)


@app.post("/compress/lossless")
async def compress_lossless(file: UploadFile = File(...)):
    _validate_pdf_upload(file)
    try:
        input_bytes = await file.read()
        original_size = len(input_bytes)
        if original_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Run CPU-bound compression in non-blocking threadpool
        output_bytes = await run_in_threadpool(_compress_lossless_bytes, input_bytes)
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lossless compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, "lossless (pypdf)", file.filename, "lossless_compressed"
    )
    return StreamingResponse(BytesIO(output_bytes), media_type="application/pdf", headers=headers)


@app.post("/compress/optimized")
async def compress_optimized(file: UploadFile = File(...)):
    """Best optimization, minimal compression (high quality)."""
    _validate_pdf_upload(file)
    try:
        input_bytes = await file.read()
        original_size = len(input_bytes)
        if original_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Run blocking process wrapper in non-blocking threadpool
        output_bytes = await run_in_threadpool(_run_ghostscript_bytes, input_bytes, "/printer")
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimized compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, "ghostscript (/printer) - minimal loss", file.filename, "optimized"
    )
    return StreamingResponse(BytesIO(output_bytes), media_type="application/pdf", headers=headers)


@app.post("/compress/little")
async def compress_little(file: UploadFile = File(...)):
    """Little loss with medium compression (balanced)."""
    _validate_pdf_upload(file)
    try:
        input_bytes = await file.read()
        original_size = len(input_bytes)
        if original_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Run blocking process wrapper in non-blocking threadpool
        output_bytes = await run_in_threadpool(_run_ghostscript_bytes, input_bytes, "/ebook")
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Little/medium compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, "ghostscript (/ebook) - medium", file.filename, "little_loss"
    )
    return StreamingResponse(BytesIO(output_bytes), media_type="application/pdf", headers=headers)


@app.post("/compress/max")
async def compress_max(file: UploadFile = File(...)):
    """Maximum compression (more loss, smallest size)."""
    _validate_pdf_upload(file)
    try:
        input_bytes = await file.read()
        original_size = len(input_bytes)
        if original_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Run blocking process wrapper in non-blocking threadpool
        output_bytes = await run_in_threadpool(_run_ghostscript_bytes, input_bytes, "/screen")
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Max compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, "ghostscript (/screen) - maximum", file.filename, "max_compressed"
    )
    return StreamingResponse(BytesIO(output_bytes), media_type="application/pdf", headers=headers)
