FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Every dependency ships as a binary wheel for this image, so no compiler is installed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
# The frontend is built beforehand (cd frontend && npm run build); see README.
COPY frontend/dist/ ./frontend/dist/

# Run unprivileged: the app only needs to read its code and write uploads to /tmp.
# Read access is granted explicitly rather than inherited from the build host's umask
# or default ACLs, which differ between Docker hosts.
RUN useradd --system --uid 10001 --no-create-home xerlock \
    && chmod -R a+rX /app /usr/local/lib/python3.12/site-packages /usr/local/bin
USER xerlock

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
