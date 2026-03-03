FROM python:3.12-slim

WORKDIR /app

COPY stdb_viewer/ stdb_viewer/
COPY server.py .

# Copy all .db files. server.py is included to prevent COPY from failing
# when no .db files are present (Docker requires at least one valid source).
COPY server.py *.db ./

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
EXPOSE ${PORT}

CMD python server.py --port ${PORT} --no-browser
