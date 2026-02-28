FROM python:3.12-slim

WORKDIR /app
COPY stdb_viewer/ stdb_viewer/
COPY server.py .

# Place your .db files next to this Dockerfile before building,
# or mount them at runtime: docker run -v /path/to/data:/app/data ...
COPY *.db ./

EXPOSE 8025
CMD ["python", "server.py"]
