FROM python:3.10-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev
COPY requirements.txt ./
COPY configs ./configs
COPY core ./core
COPY services ./services
#COPY templates ./templates
#COPY tests ./tests
COPY configs/settings_dev.yml ./configs/settings_dev.yml
COPY configs/settings_prod.yml ./configs/app_settings_prod.yml
COPY test_main.http ./
COPY main.py ./main.py
RUN pip3 install --no-cache-dir  --upgrade -r ./requirements.txt
# Create a volume for the application data
VOLUME ./configs
VOLUME /gpfs
VOLUME /app/data
# Set the environment variable for the data directory
ENV DATA_DIR=/app/data
# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=main:app
ENV APP_ENV=production

# Expose port 80
EXPOSE 80

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
