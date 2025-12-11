from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import tempfile
import subprocess
import shutil
import os

app = FastAPI(
    title="Selfhost PDF Compressor Tool - FastAPI",
    description=(
        "Selfhost PDF Compressor Tool (FastAPI). "
        "Provides lossless compression (PyPDF2) and optional lossy optimizations via Ghostscript "
        "with endpoints: /compress/lossless, /compress/optimized, /compress/little, /compress/max."
    ),
)


@app.get("/ping")
async def ping():
    return {"status": "ok", "project": "Selfhost PDF Compressor Tool - FastAPI"}


def _validate_pdf_upload(file: UploadFile):
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")


async def _compress_lossless_bytes(input_bytes: bytes) -> bytes:
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

        output_bytes = await _compress_lossless_bytes(input_bytes)
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lossless compression failed: {e}")

    headers = {
        "Content-Disposition": f'attachment; filename="lossless_compressed_{file.filename}"',
        "X-Original-Size": str(original_size),
        "X-Compressed-Size": str(compressed_size),
        "X-Compression-Method": "lossless (PyPDF2)",
    }
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

        # minimal compression / high quality -> use Ghostscript /printer or /prepress
        output_bytes = _run_ghostscript_bytes(input_bytes, "/printer")
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimized compression failed: {e}")

    headers = {
        "Content-Disposition": f'attachment; filename="optimized_{file.filename}"',
        "X-Original-Size": str(original_size),
        "X-Compressed-Size": str(compressed_size),
        "X-Compression-Method": "ghostscript (/printer) - minimal loss",
    }
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

        # medium compression -> /ebook
        output_bytes = _run_ghostscript_bytes(input_bytes, "/ebook")
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Little/medium compression failed: {e}")

    headers = {
        "Content-Disposition": f'attachment; filename="little_loss_{file.filename}"',
        "X-Original-Size": str(original_size),
        "X-Compressed-Size": str(compressed_size),
        "X-Compression-Method": "ghostscript (/ebook) - medium",
    }
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

        # maximum compression -> /screen (low res)
        output_bytes = _run_ghostscript_bytes(input_bytes, "/screen")
        compressed_size = len(output_bytes)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Max compression failed: {e}")

    headers = {
        "Content-Disposition": f'attachment; filename="max_compressed_{file.filename}"',
        "X-Original-Size": str(original_size),
        "X-Compressed-Size": str(compressed_size),
        "X-Compression-Method": "ghostscript (/screen) - maximum",
    }
    return StreamingResponse(BytesIO(output_bytes), media_type="application/pdf", headers=headers)