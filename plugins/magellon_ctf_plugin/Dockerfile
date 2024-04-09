FROM python:3.10-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev
RUN apt-get install -y graphviz nano wget
RUN pip install psycopg2-binary --no-cache-dir

COPY requirements.txt ./
RUN pip3 install --no-cache-dir  --upgrade -r ./requirements.txt

#COPY . .
COPY appionlib ./appionlib
COPY assets ./assets
COPY configs ./configs
COPY configs/settings_dev.yml ./configs/settings_dev.yml
COPY configs/settings_prod.yml ./configs/settings_prod.yml
COPY core ./core
COPY core/rabbitmq ./core/rabbitmq
COPY pyami ./pyami
COPY service ./service
COPY tests ./tests
COPY main.py ./main.py

#COPY core/logger_config.py ./core/logger_config.py
#COPY core/settings.py ./core/settings.py

COPY ctffind ./ctffind
COPY ctffind_plot_results.sh ./ctffind_plot_results.sh
COPY test_main.http ./
COPY test_publish.py ./test_publish.py
COPY utils.py ./utils.py

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
