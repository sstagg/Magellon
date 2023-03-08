# syntax=docker/dockerfile:1
#https://www.freecodecamp.org/news/how-to-dockerize-a-flask-app/
#https://github.com/Dev-Elie/Flask-Docker-App
FROM python:3.10-slim-buster

WORKDIR /usr/src/app

#COPY ../../MainService/requirements.txt requirements.txt
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt
#RUN pip3 install /en_core_web_sm-2.0.0.tar.gz

#COPY . .
COPY app.py ./
COPY requirements.txt ./
COPY leginon ./
COPY lib ./
COPY sinedon ./
COPY tests ./
COPY pyami ./

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]