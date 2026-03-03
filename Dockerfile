FROM python:3.12-slim

WORKDIR /app

COPY stdb_viewer/ stdb_viewer/
COPY server.py .

# Copy all .db files alongside server.py (which is guaranteed to exist)
# This ensures COPY doesn't fail even if no .db files are present
COPY server.py *.db ./

ENV PORT=8080
EXPOSE ${PORT}

CMD python server.py --port ${PORT} --no-browser
