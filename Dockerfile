FROM python:3.12-slim

WORKDIR /app

# Copy application code
COPY stdb_viewer/ stdb_viewer/
COPY server.py .

# Copy database files (place your .db files in the repo root before building)
COPY *.db ./

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
EXPOSE ${PORT}

# Use --no-browser and read PORT from environment
CMD python server.py --port ${PORT} --no-browser
