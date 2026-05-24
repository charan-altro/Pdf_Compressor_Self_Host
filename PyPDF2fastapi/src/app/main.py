from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
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
        "Access-Control-Expose-Headers": "X-Original-Size, X-Compressed-Size, X-Saved-Size, X-Savings-Percentage, X-Compression-Method"
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    html_content = """
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Selfhost PDF Compressor</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            .drag-over {
                border-color: #3b82f6;
                background-color: rgba(59, 130, 246, 0.05);
            }
        </style>
    </head>
    <body class="bg-gray-900 text-gray-100 min-h-screen flex flex-col justify-between font-sans">
        
        <!-- Header -->
        <header class="border-b border-gray-800 bg-gray-900/50 backdrop-blur-md sticky top-0 z-50 py-4 px-6">
            <div class="max-w-5xl mx-auto flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="bg-gradient-to-tr from-blue-600 to-indigo-600 p-2 rounded-lg text-white">
                        <i class="fa-solid fa-file-pdf text-xl"></i>
                    </div>
                    <span class="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                        Selfhost PDF Compressor
                    </span>
                </div>
                <div class="flex items-center space-x-4">
                    <span class="text-xs bg-gray-800 px-3 py-1 rounded-full text-gray-400 border border-gray-700 flex items-center gap-1">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> FastAPI + Swarm
                    </span>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="max-w-3xl mx-auto w-full px-6 py-12 flex-grow flex flex-col justify-center">
            
            <div class="bg-gray-800/40 border border-gray-800 rounded-2xl p-8 backdrop-blur-md shadow-2xl">
                
                <!-- Step 1: Upload Box -->
                <div id="drop-zone" class="border-2 border-dashed border-gray-700 hover:border-gray-500 transition-all rounded-xl p-10 text-center cursor-pointer flex flex-col items-center justify-center space-y-4">
                    <input type="file" id="file-input" accept=".pdf" class="hidden">
                    <div class="bg-gray-800/80 p-4 rounded-full text-blue-500 shadow-inner">
                        <i class="fa-solid fa-cloud-arrow-up text-3xl"></i>
                    </div>
                    <div>
                        <p class="text-base font-semibold text-gray-200">Drag & drop your PDF file here</p>
                        <p class="text-sm text-gray-400 mt-1">or click to browse from files</p>
                    </div>
                    <div class="text-xs text-gray-500">Only PDF files are supported</div>
                </div>

                <!-- File Info Card (hidden initially) -->
                <div id="file-info" class="hidden bg-gray-800/80 border border-gray-700 rounded-xl p-4 mt-6 flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <i class="fa-solid fa-file-pdf text-red-500 text-2xl"></i>
                        <div>
                            <p id="file-name" class="text-sm font-semibold truncate max-w-xs md:max-w-md text-gray-200"></p>
                            <p id="file-size" class="text-xs text-gray-400"></p>
                        </div>
                    </div>
                    <button id="remove-file" class="text-gray-400 hover:text-red-500 transition-colors p-1.5 rounded-lg hover:bg-gray-700">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>

                <!-- Compression Options -->
                <div class="mt-8 space-y-4">
                    <label class="block text-sm font-medium text-gray-400 mb-2">Select Compression Method</label>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <!-- Option 1: Lossless -->
                        <label class="relative flex p-4 border border-gray-700 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-gray-800/30 transition-all">
                            <input type="radio" name="method" value="/compress/lossless" checked class="sr-only">
                            <div class="flex items-start">
                                <div class="flex items-center h-5 mt-0.5">
                                    <span class="w-4 h-4 rounded-full border border-gray-600 flex items-center justify-center mr-3 radio-indicator bg-blue-500 border-blue-500"><span class="w-2 h-2 rounded-full bg-white"></span></span>
                                </div>
                                <div class="text-sm">
                                    <p class="font-semibold text-gray-200">Lossless (Safe)</p>
                                    <p class="text-xs text-gray-400 mt-0.5">No quality loss, perfect for scans and docs with structured streams.</p>
                                </div>
                            </div>
                        </label>

                        <!-- Option 2: Optimized -->
                        <label class="relative flex p-4 border border-gray-700 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-gray-800/30 transition-all">
                            <input type="radio" name="method" value="/compress/optimized" class="sr-only">
                            <div class="flex items-start">
                                <div class="flex items-center h-5 mt-0.5">
                                    <span class="w-4 h-4 rounded-full border border-gray-600 flex items-center justify-center mr-3 radio-indicator"></span>
                                </div>
                                <div class="text-sm">
                                    <p class="font-semibold text-gray-200">Optimized (High Quality)</p>
                                    <p class="text-xs text-gray-400 mt-0.5">Excellent balance, professional quality vector settings via GS printer.</p>
                                </div>
                            </div>
                        </label>

                        <!-- Option 3: Balanced -->
                        <label class="relative flex p-4 border border-gray-700 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-gray-800/30 transition-all">
                            <input type="radio" name="method" value="/compress/little" class="sr-only">
                            <div class="flex items-start">
                                <div class="flex items-center h-5 mt-0.5">
                                    <span class="w-4 h-4 rounded-full border border-gray-600 flex items-center justify-center mr-3 radio-indicator"></span>
                                </div>
                                <div class="text-sm">
                                    <p class="font-semibold text-gray-200">Balanced (Medium)</p>
                                    <p class="text-xs text-gray-400 mt-0.5">Perfect for E-Books and emails, 150 DPI target via GS ebook.</p>
                                </div>
                            </div>
                        </label>

                        <!-- Option 4: Max -->
                        <label class="relative flex p-4 border border-gray-700 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-gray-800/30 transition-all">
                            <input type="radio" name="method" value="/compress/max" class="sr-only">
                            <div class="flex items-start">
                                <div class="flex items-center h-5 mt-0.5">
                                    <span class="w-4 h-4 rounded-full border border-gray-600 flex items-center justify-center mr-3 radio-indicator"></span>
                                </div>
                                <div class="text-sm">
                                    <p class="font-semibold text-gray-200">Max Compression</p>
                                    <p class="text-xs text-gray-400 mt-0.5">Smallest file size possible, low resolution screen mode (72 DPI).</p>
                                </div>
                            </div>
                        </label>
                    </div>
                </div>

                <!-- Progress / Loader (hidden initially) -->
                <div id="loader-section" class="hidden mt-8 space-y-3">
                    <div class="flex justify-between text-xs text-gray-400">
                        <span id="loader-text">Compressing PDF streams...</span>
                        <span id="progress-percent">0%</span>
                    </div>
                    <div class="w-full bg-gray-800 rounded-full h-2 overflow-hidden border border-gray-700">
                        <div id="progress-bar" class="bg-gradient-to-r from-blue-500 to-indigo-500 h-full w-0 transition-all duration-300"></div>
                    </div>
                </div>

                <!-- Action Button -->
                <div class="mt-8">
                    <button id="compress-btn" disabled class="w-full py-4 bg-gray-700 text-gray-400 cursor-not-allowed font-semibold rounded-xl flex items-center justify-center space-x-2 transition-all shadow-lg shadow-blue-500/10">
                        <i class="fa-solid fa-compress mr-1"></i>
                        <span>Select a file first</span>
                    </button>
                </div>

                <!-- Results Block (hidden initially) -->
                <div id="results-card" class="hidden mt-8 border-t border-gray-800 pt-8 space-y-6">
                    <h3 id="res-title" class="text-lg font-bold text-gray-100 flex items-center gap-2">
                        <i class="fa-solid fa-circle-check text-emerald-500"></i> Compression Completed!
                    </h3>
                    
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="bg-gray-800/30 p-4 border border-gray-800 rounded-xl">
                            <p class="text-xs text-gray-400">Before</p>
                            <p id="res-original" class="text-lg font-bold text-gray-200 mt-1"></p>
                        </div>
                        <div class="bg-gray-800/30 p-4 border border-gray-800 rounded-xl">
                            <p class="text-xs text-gray-400">After</p>
                            <p id="res-compressed" class="text-lg font-bold text-gray-200 mt-1"></p>
                        </div>
                        <div class="bg-gray-800/30 p-4 border border-gray-800 rounded-xl">
                            <p id="lbl-saved" class="text-xs text-gray-400">Saved</p>
                            <p id="res-saved" class="text-lg font-bold text-emerald-400 mt-1"></p>
                        </div>
                        <div class="bg-gray-800/30 p-4 border border-gray-800 rounded-xl">
                            <p class="text-xs text-gray-400">Ratio</p>
                            <p id="res-ratio" class="text-lg font-bold text-blue-400 mt-1"></p>
                        </div>
                    </div>

                    <div class="bg-gray-800/20 border border-gray-800 rounded-xl p-3 text-xs text-gray-400 flex items-center justify-between">
                        <span>Method: <strong id="res-method" class="text-gray-300"></strong></span>
                    </div>

                    <a id="download-link" href="#" download class="w-full py-4 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 font-semibold rounded-xl flex items-center justify-center space-x-2 transition-all shadow-lg shadow-emerald-500/20 text-white">
                        <i class="fa-solid fa-download"></i>
                        <span>Download Compressed PDF</span>
                    </a>
                </div>

            </div>

        </main>

        <!-- Footer -->
        <footer class="border-t border-gray-800 py-6 px-6 text-center text-xs text-gray-500">
            <div class="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                <span>Selfhost PDF Compressor Tool — Phase 2</span>
                <span class="flex items-center gap-1"><i class="fa-solid fa-code text-indigo-500"></i> Engineered beautifully by AI_Hermy for Cherry</span>
            </div>
        </footer>

        <!-- Core Interactive Script -->
        <script>
            const dropZone = document.getElementById('drop-zone');
            const fileInput = document.getElementById('file-input');
            const fileInfo = document.getElementById('file-info');
            const fileName = document.getElementById('file-name');
            const fileSize = document.getElementById('file-size');
            const removeFileBtn = document.getElementById('remove-file');
            const compressBtn = document.getElementById('compress-btn');
            const loaderSection = document.getElementById('loader-section');
            const progressBar = document.getElementById('progress-bar');
            const progressPercent = document.getElementById('progress-percent');
            const loaderText = document.getElementById('loader-text');
            const resultsCard = document.getElementById('results-card');
            const radios = document.getElementsByName('method');
            
            let selectedFile = null;

            // Absolute Safe Bytes Formatting (Handles Negative Values!)
            function formatBytes(bytes) {
                if (bytes === 0) return '0 Bytes';
                const isNegative = bytes < 0;
                const absBytes = Math.abs(bytes);
                const k = 1024;
                const i = Math.floor(Math.log(absBytes) / Math.log(k));
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const formatted = parseFloat((absBytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
                return isNegative ? '-' + formatted : formatted;
            }

            // Drag and Drop handlers
            ['dragenter', 'dragover'].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dropZone.classList.add('drag-over');
                }, false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropZone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    dropZone.classList.remove('drag-over');
                }, false);
            });

            dropZone.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length) handleFiles(files[0]);
            }, false);

            dropZone.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length) handleFiles(e.target.files[0]);
            });

            // Radio styling behavior
            radios.forEach(radio => {
                radio.addEventListener('change', (e) => {
                    // Update radio indicator classes
                    document.querySelectorAll('.radio-indicator').forEach(el => {
                        el.className = "w-4 h-4 rounded-full border border-gray-600 flex items-center justify-center mr-3 radio-indicator";
                        el.innerHTML = "";
                    });
                    const parent = e.target.closest('label');
                    const indicator = parent.querySelector('.radio-indicator');
                    indicator.className = "w-4 h-4 rounded-full border border-blue-500 flex items-center justify-center mr-3 radio-indicator bg-blue-500";
                    indicator.innerHTML = '<span class="w-2 h-2 rounded-full bg-white"></span>';
                });
            });

            function handleFiles(file) {
                if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
                    alert('Please upload a PDF file only.');
                    return;
                }
                selectedFile = file;
                fileName.textContent = file.name;
                fileSize.textContent = formatBytes(file.size);
                
                dropZone.classList.add('hidden');
                fileInfo.classList.remove('hidden');
                
                compressBtn.removeAttribute('disabled');
                compressBtn.className = "w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 font-semibold rounded-xl flex items-center justify-center space-x-2 transition-all shadow-lg shadow-blue-500/20 text-white cursor-pointer";
                compressBtn.querySelector('span').textContent = "Compress PDF";
                
                resultsCard.classList.add('hidden');
            }

            removeFileBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                selectedFile = null;
                fileInput.value = '';
                
                dropZone.classList.remove('hidden');
                fileInfo.classList.add('hidden');
                
                compressBtn.setAttribute('disabled', 'true');
                compressBtn.className = "w-full py-4 bg-gray-700 text-gray-400 cursor-not-allowed font-semibold rounded-xl flex items-center justify-center space-x-2 transition-all shadow-lg shadow-blue-500/10";
                compressBtn.querySelector('span').textContent = "Select a file first";
                
                resultsCard.classList.add('hidden');
                loaderSection.classList.add('hidden');
            });

            compressBtn.addEventListener('click', async () => {
                if (!selectedFile) return;

                // Reset loader
                loaderSection.classList.remove('hidden');
                resultsCard.classList.add('hidden');
                progressBar.style.width = '20%';
                progressPercent.textContent = '20%';
                loaderText.textContent = "Reading PDF content...";
                compressBtn.setAttribute('disabled', 'true');
                
                const selectedMethod = Array.from(radios).find(r => r.checked).value;
                const formData = new FormData();
                formData.append('file', selectedFile);

                try {
                    progressBar.style.width = '45%';
                    progressPercent.textContent = '45%';
                    loaderText.textContent = "Running stream optimizations...";

                    const response = await fetch(selectedMethod, {
                        method: 'POST',
                        body: formData
                    });

                    progressBar.style.width = '80%';
                    progressPercent.textContent = '80%';
                    loaderText.textContent = "Generating compressed metadata...";

                    if (!response.ok) {
                        const errorText = await response.text();
                        let parsedErr = "Compression failed";
                        try { parsedErr = JSON.parse(errorText).detail; } catch(_) {}
                        throw new Error(parsedErr);
                    }

                    const blob = await response.blob();
                    
                    // Fetch customized analytics headers
                    const original = parseInt(response.headers.get('X-Original-Size')) || selectedFile.size;
                    const compressed = parseInt(response.headers.get('X-Compressed-Size')) || blob.size;
                    const saved = parseInt(response.headers.get('X-Saved-Size')) || (original - compressed);
                    const ratio = response.headers.get('X-Savings-Percentage') || '0%';
                    const method = response.headers.get('X-Compression-Method') || "pypdf";

                    // Update UI stats
                    document.getElementById('res-original').textContent = formatBytes(original);
                    document.getElementById('res-compressed').textContent = formatBytes(compressed);
                    document.getElementById('res-saved').textContent = formatBytes(saved);
                    document.getElementById('res-ratio').textContent = ratio;
                    document.getElementById('res-method').textContent = method;

                    // Style depending on savings
                    const resTitle = document.getElementById('res-title');
                    const resSaved = document.getElementById('res-saved');
                    const lblSaved = document.getElementById('lbl-saved');
                    
                    if (saved <= 0) {
                        resTitle.innerHTML = '<i class="fa-solid fa-circle-exclamation text-amber-500"></i> File is already fully optimized!';
                        lblSaved.textContent = "Difference";
                        resSaved.className = "text-lg font-bold text-amber-500 mt-1";
                        resSaved.textContent = "0 Bytes";
                        document.getElementById('res-ratio').textContent = "0.0%";
                    } else {
                        resTitle.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-500"></i> Compression Completed!';
                        lblSaved.textContent = "Saved";
                        resSaved.className = "text-lg font-bold text-emerald-400 mt-1";
                    }

                    // Set Download Link
                    const downloadUrl = URL.createObjectURL(blob);
                    const downloadLink = document.getElementById('download-link');
                    downloadLink.href = downloadUrl;
                    downloadLink.download = "compressed_" + selectedFile.name;

                    // Finish progress animation
                    progressBar.style.width = '100%';
                    progressPercent.textContent = '100%';
                    loaderText.textContent = "Finished!";
                    
                    setTimeout(() => {
                        loaderSection.classList.add('hidden');
                        resultsCard.classList.remove('hidden');
                        compressBtn.removeAttribute('disabled');
                    }, 500);

                } catch (error) {
                    alert("Error: " + error.message);
                    progressBar.style.width = '0%';
                    progressPercent.textContent = '0%';
                    loaderSection.classList.add('hidden');
                    compressBtn.removeAttribute('disabled');
                }
            });
        </script>
    </body>
    </html>
    """
    return html_content


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

        # Smart fallback: if compression increases size, return the original
        if compressed_size >= original_size:
            output_bytes = input_bytes
            compressed_size = original_size
            method_desc = "lossless (pypdf) - already optimized"
        else:
            method_desc = "lossless (pypdf)"

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lossless compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, method_desc, file.filename, "lossless_compressed"
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

        # Smart fallback: if compression increases size, return the original
        if compressed_size >= original_size:
            output_bytes = input_bytes
            compressed_size = original_size
            method_desc = "ghostscript (/printer) - already optimized"
        else:
            method_desc = "ghostscript (/printer) - minimal loss"

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimized compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, method_desc, file.filename, "optimized"
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

        # Smart fallback: if compression increases size, return the original
        if compressed_size >= original_size:
            output_bytes = input_bytes
            compressed_size = original_size
            method_desc = "ghostscript (/ebook) - already optimized"
        else:
            method_desc = "ghostscript (/ebook) - medium"

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Little/medium compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, method_desc, file.filename, "little_loss"
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

        # Smart fallback: if compression increases size, return the original
        if compressed_size >= original_size:
            output_bytes = input_bytes
            compressed_size = original_size
            method_desc = "ghostscript (/screen) - already optimized"
        else:
            method_desc = "ghostscript (/screen) - maximum"

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Max compression failed: {e}")

    headers = _calculate_savings_headers(
        original_size, compressed_size, method_desc, file.filename, "max_compressed"
    )
    return StreamingResponse(BytesIO(output_bytes), media_type="application/pdf", headers=headers)
