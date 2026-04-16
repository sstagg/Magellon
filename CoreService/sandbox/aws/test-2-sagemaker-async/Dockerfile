# SageMaker-compatible container for async inference. Adds a FastAPI server over the base image.
# SM contract: /ping (GET) → 200 OK, /invocations (POST) → process + respond. Listen on 8080.
ARG BASE_IMAGE
FROM --platform=linux/amd64 ${BASE_IMAGE}

RUN pip3 install --no-cache-dir fastapi==0.115.* uvicorn[standard]==0.32.*

COPY server.py /app/server.py

EXPOSE 8080
ENV PYTHONUNBUFFERED=1

# SageMaker runs `serve` by default, so provide that shim.
RUN printf '#!/bin/bash\nexec uvicorn --host 0.0.0.0 --port 8080 server:app\n' > /usr/local/bin/serve && \
    chmod +x /usr/local/bin/serve

ENTRYPOINT []
CMD ["serve"]
