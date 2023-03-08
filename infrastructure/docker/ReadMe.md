

## Docker Build & Run
docker build .
docker build -t khoshbin/magellon-main-service .
docker build -t khoshbin/magellon-main-service infrastructure/docker/


sudo docker run -it -p3000:5000 behdad/flask01
sudo docker run -d -p3000:5000 behdad/flask01

docker run --rm -it -p 15672:15672 -p 5672:5672 rabbitmq:3-management

## Docker-Compose
sudo docker-compose build
sudo docker-compose up


https://blog.carlesmateo.com/2022/07/20/creating-a-rabbitmq-docker-container-accessed-with-python-and-pika/

