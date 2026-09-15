FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the sentence-transformers model into the image so the first
# /matching/recommend after a deploy doesn't block on a ~90 MB download
# (and so the container needs no write access to a HF cache at runtime).
ENV HF_HOME=/opt/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000

# --proxy-headers makes Starlette trust nginx's X-Forwarded-Proto (see
# deploy/nginx/spacio.conf) so redirects it generates (e.g. FastAPI's
# trailing-slash redirect) are built as https:// behind TLS-terminating
# nginx, not http:// — an http:// redirect from an https:// page is mixed
# content and gets silently blocked by browsers, breaking any route that
# gets hit without its exact trailing slash. --forwarded-allow-ips='*' is
# safe here since the container's port is bound to 127.0.0.1 only
# (docker-compose.prod.yml) — nothing but nginx on the same host can reach
# it directly.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
