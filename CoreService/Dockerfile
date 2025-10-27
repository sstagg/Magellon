# syntax=docker/dockerfile:1
#https://www.freecodecamp.org/news/how-to-dockerize-a-flask-app/
#https://github.com/Dev-Elie/Flask-Docker-App
FROM python:3.11-slim-bookworm

WORKDIR /app

#COPY ../../MainService/requirements.txt requirements.txt
COPY requirements.txt ./

RUN apt-get update && apt-get install -y libpq-dev
RUN apt-get install -y graphviz nano wget
RUN pip3 install --upgrade pip
RUN pip install psycopg2-binary --no-cache-dir
RUN pip3 install --no-cache-dir --upgrade -r ./requirements.txt
#RUN pip3 install /en_core_web_sm-2.0.0.tar.gz

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
COPY core ./core
COPY static ./static
COPY dependencies ./dependencies

COPY configs/app_settings_dev.yaml ./configs/app_settings_dev.yaml
COPY configs/app_settings_prod.yaml ./configs/app_settings_prod.yaml
COPY logger_config.py ./logger_config.py
COPY config.py ./config.py
COPY database.py ./database.py
COPY test_main.http ./

# Create a volume for the application data
VOLUME /magellon
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
#CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0","--port=80"]
# Start the application using Uvicorn ASGI server
#uvicorn main:app --host 0.0.0.0 --port 8181
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
#CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--reload", "--reload-dir", "/app"]
#If you are running your container behind a TLS Termination Proxy (load balancer) like Nginx or Traefik, add the option --proxy-headers, this will tell Uvicorn to trust the headers sent by that proxy telling it that the application is running behind HTTPS, etc.
#CMD ["uvicorn", "main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
