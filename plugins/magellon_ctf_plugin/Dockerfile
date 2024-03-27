FROM python:3.13-slim-buster

WORKDIR /app

COPY requirements.txt ./

RUN apt-get update && apt-get install -y libpq-dev
RUN apt-get install -y graphviz nano wget
RUN pip install psycopg2-binary --no-cache-dir
RUN pip3 install --no-cache-dir  --upgrade -r ./requirements.txt

#COPY . .
COPY main.py ./main.py
#COPY requirements.txt ./
#COPY areas ./app
COPY controllers ./controllers
COPY lib ./lib
COPY models ./models
COPY repositories ./repositories
COPY services ./services
COPY templates ./templates
COPY tests ./tests
COPY configs ./configs

COPY configs/settings_dev.yml ./configs/settings_dev.yml
COPY configs/settings_prod.yml ./configs/settings_prod.yml

COPY core/logger_config.py ./core/logger_config.py
COPY core/settings.py ./core/settings.py

COPY database.py ./database.py
COPY test_main.http ./

# Create a volume for the application data
VOLUME /app/data
VOLUME ./configs
VOLUME /gpfs

# Set the environment variable for the data directory
ENV DATA_DIR=/app/data

# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=main:app

ENV APP_ENV=production

# Expose port 80
EXPOSE 80

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
