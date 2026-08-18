FROM python:3.14.7-alpine@sha256:05b2b8b732ecd268fee8727a369f936f022d1321b59befd13c30ede22769dcdc

# DejaVu is the render font; Pillow needs a real TTF and the image ships none.
RUN apk add --no-cache font-dejavu
ENV DASHINK_FONT_DIR=/usr/share/fonts/dejavu

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && rm -rf /usr/local/lib/python*/site-packages/pip* \
           /usr/local/lib/python*/site-packages/setuptools* \
           /usr/local/lib/python*/site-packages/pkg_resources

COPY server/ ./

RUN addgroup -S dashink \
 && adduser -S -u 10001 -G dashink -h /home/dashink dashink \
 && chmod 700 /home/dashink
USER dashink

EXPOSE 8099

# One worker, two threads: renders are ~100ms and the only client is a Kindle
# waking up every few minutes. More workers would just duplicate the caches.
CMD ["gunicorn", "--bind", "0.0.0.0:8099", "--workers", "1", "--threads", "2", \
     "--access-logfile", "-", "app:app"]
