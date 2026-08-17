FROM python:3.14.6-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

# DejaVu is the render font; Pillow needs a real TTF and slim images ship none.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./

RUN useradd --system --create-home --home-dir /home/dashink --uid 10001 dashink
USER dashink

EXPOSE 8099

# One worker, two threads: renders are ~100ms and the only client is a Kindle
# waking up every few minutes. More workers would just duplicate the caches.
CMD ["gunicorn", "--bind", "0.0.0.0:8099", "--workers", "1", "--threads", "2", \
     "--access-logfile", "-", "app:app"]
