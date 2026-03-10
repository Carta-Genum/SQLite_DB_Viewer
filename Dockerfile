FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir google-cloud-storage

COPY stdb_viewer/ stdb_viewer/
COPY server.py .
COPY cloud/ cloud/

ENV PORT=8025
EXPOSE ${PORT}
CMD ["sh", "-c", "python cloud/startup.py && python server.py --port ${PORT} --no-browser"]
