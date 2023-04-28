# syntax=docker/dockerfile:1
#https://www.freecodecamp.org/news/how-to-dockerize-a-flask-app/
#https://github.com/Dev-Elie/Flask-Docker-App
FROM python:3.10-slim-buster

WORKDIR /app

#COPY ../../MainService/requirements.txt requirements.txt
COPY requirements.txt ./
RUN pip3 install --no-cache-dir  --upgrade -r ./requirements.txt
#RUN pip3 install /en_core_web_sm-2.0.0.tar.gz

#COPY . .
COPY main.py ./app
#COPY requirements.txt ./
COPY areas ./app
COPY controllers ./controllers
COPY lib ./lib
COPY models ./models
COPY repositories ./repositories
COPY services ./services
COPY templates ./templates
COPY tests ./tests
COPY config.py ./config.py
COPY database.py ./database.py
COPY logger_config.py ./logger_config.py
COPY test_main.http ./


# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=app.main:app

# Expose port 80
EXPOSE 80
#CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0","--port=80"]
# Start the application using Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
#If you are running your container behind a TLS Termination Proxy (load balancer) like Nginx or Traefik, add the option --proxy-headers, this will tell Uvicorn to trust the headers sent by that proxy telling it that the application is running behind HTTPS, etc.
#CMD ["uvicorn", "app.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
