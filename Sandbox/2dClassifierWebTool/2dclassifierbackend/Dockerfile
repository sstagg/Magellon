FROM python:3.12.4-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libhdf5-dev \
    libgl1-mesa-glx \
    libsqlite3-dev \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY main.py utils.py script.py scriptUtils.py requirements.txt /app/

COPY 2dclass_evaluator /app/2dclass_evaluator

# install numpy first to ensure h5py builds (only if you stay on 3.12)
RUN pip install numpy==1.26.4

# use h5py with prebuilt wheels
RUN pip install --only-binary=h5py --no-cache-dir h5py==3.12.1

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
ENV UPLOAD_DIR=/app/uploads
VOLUME ["/app/uploads"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
