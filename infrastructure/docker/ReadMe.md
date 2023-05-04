
## Commands to manually run:
uvicorn main:app --reload
uvicorn main:app --host 0.0.0.0 --port 8181

## Docker Build & Run
`docker build .
docker build -t khoshbin/magellon-main-service .
docker build -t khoshbin/magellon-main-service infrastructure/docker/
`

`gh repo clone sstagg/Magellon`

### Go to CoreService directory and run:
`sudo docker build --no-cache -f ../infrastructure/docker/Dockerfile -t khoshbin/magellon-main-service ./`

`docker push khoshbin/magellon-main-service`

from imagename:khoshbin/magellon-main-service
then enable https --> Force https --> continer http port 80
https://api.magellon.org/openapi

`sudo docker pull --no-cache khoshbin/magellon-main-service
sudo docker run -it -p8080:80 khoshbin/magellon-main-service
sudo docker run -d --restart=always -p 8080:80 khoshbin/magellon-main-service
`
OrangeFlag51!

`
sudo docker run -it -p3000:5000 behdad/flask01
sudo docker run -d --restart=always -p 8080:80 -v /tmp/filesystem/hostPath:/app/data  -e DATA_DIR=/app/data khoshbin/magellon-main-service
`
Note that you can also use a separate environment file to set multiple environment variables. To do this, you can use the --env-file option of the docker run command to specify a file containing environment variable definitions. For example:
`docker run --env-file my_env_file my_image`
### Go to WebApp directory and run:


`docker run --rm -it -p 15672:15672 -p 5672:5672 rabbitmq:3-management`

## Docker-Compose
`sudo docker-compose build
sudo docker-compose up`


https://blog.carlesmateo.com/2022/07/20/creating-a-rabbitmq-docker-container-accessed-with-python-and-pika/

