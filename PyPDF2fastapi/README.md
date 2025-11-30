# Selfhost PDF Compressor Tool - FastAPI

A small FastAPI service to compress PDFs. Supports:
- Lossless compression (PyPDF2): `/compress/lossless` (alias `/compress`)
- Optimized (minimal loss): `/compress/optimized` (Ghostscript `/printer`)
- Little loss / medium: `/compress/little` (Ghostscript `/ebook`)
- Maximum compression: `/compress/max` (Ghostscript `/screen`)

Prerequisites
- Docker & docker-compose (or Docker buildx for multi-arch)
- (Optional) Ghostscript: can be included at image-build time

Build (with Ghostscript included; use host network if build environment has DNS issues)
- docker build --network=host --build-arg INSTALL_GS=true -t <DOCKERHUB_USER>/selfhost-pdf-compressor:latest -f src/Dockerfile .
- OR with compose (ensure build.network host works in your environment):
  - docker-compose build --no-cache
  - docker-compose up -d

Run (docker-compose)
- docker-compose up -d
- Check logs: docker-compose logs -f web
- Health: curl http://localhost:8002/ping

Run (docker)
- docker run -d --name selfhost -p 8002:8000 <DOCKERHUB_USER>/selfhost-pdf-compressor:latest
- docker logs -f selfhost

Usage examples (replace sample.pdf)
- Lossless:
  curl -X POST -F "file=@sample.pdf" http://localhost:8002/compress/lossless -o out_lossless.pdf
- Optimized (minimal loss):
  curl -X POST -F "file=@sample.pdf" http://localhost:8002/compress/optimized -o out_optimized.pdf
- Little (medium):
  curl -X POST -F "file=@sample.pdf" http://localhost:8002/compress/little -o out_little.pdf
- Max (maximum compression):
  curl -X POST -F "file=@sample.pdf" http://localhost:8002/compress/max -o out_max.pdf

Notes
- Ghostscript endpoints return 503 if Ghostscript is not installed in the container.
- For Raspberry Pi: build multi-arch image with buildx and push to Docker Hub:
  - docker buildx create --use --bootstrap
  - docker buildx build --platform linux/arm/v7,linux/arm64,linux/amd64 -t <DOCKERHUB_USER>/selfhost-pdf-compressor:latest --push -f src/Dockerfile .
- Leave `INSTALL_GS=false` during build to skip Ghostscript (smaller offline-friendly image).

Replace `<DOCKERHUB_USER>` with your Docker Hub username when tagging/pushing.

