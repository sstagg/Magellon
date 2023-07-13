
## Commands to manually run:
uvicorn main:app --reload
uvicorn main:app --host 0.0.0.0 --port 8181

## Docker Build & Run
`docker build .
docker build -t khoshbin/magellon-main-service .
docker build -t khoshbin/magellon-main-service infrastructure/docker/
`


rm -rf "/home/behdad/projects/Magellon/"
cd /home/behdad/projects
`gh repo clone sstagg/Magellon`
cd Magellon/CoreService/
### Go to CoreService directory and run:
`
sudo docker build --no-cache -f ../infrastructure/docker/Dockerfile -t khoshbin/magellon-main-service ./
sudo docker run -d --restart=always  --name magellon-core-service01 --network magellon -p 8000:80 -v /mnt/hpc:/app/data  -e DATA_DIR=/app/data khoshbin/magellon-main-service
sudo docker run -it -p8080:80 -v /mnt/hpc:/app/data khoshbin/magellon-main-service bash
docker push khoshbin/magellon-main-service
sudo docker exec -it <container_id> bash
`

from imagename:khoshbin/magellon-main-service
then enable https --> Force https --> continer http port 80
https://api.magellon.org/openapi



sudo apt-get update
sudo apt-get install sshfs

sudo ufw allow 8181
sudo mount -t cifs //hpc-login.rcc.fsu.edu/gpfs/research/stagg/leginondata/22apr01a/22apr01a/rawdata /mnt/hpc -o username=bk22n,password=in#232
sudo sshfs bk22n@hpc-login.rcc.fsu.edu:/gpfs/research/stagg/leginondata/22apr01a/22apr01a/rawdata /mnt/hpc
`
sudo mkdir /mnt/hpc
sudo docker run -it -p8080:80 -v /mnt/hpc:/app/data khoshbin/magellon-main-service bash
sudo docker pull --no-cache khoshbin/magellon-main-service
sudo docker run -it -p8080:80 khoshbin/magellon-main-service
sudo docker run -d --restart=always -p 8080:80 khoshbin/magellon-main-service
`
docker ps


OrangeFlag51!

Note that you can also use a separate environment file to set multiple environment variables. To do this, you can use the --env-file option of the docker run command to specify a file containing environment variable definitions. For example:
`docker run --env-file my_env_file my_image`
### Go to WebApp directory and run:

ng build --prod

`
sudo docker build --no-cache  --build-arg API_URL="http://128.186.103.43:8000/web/" -f ../infrastructure/docker/angular/Dockerfile -t khoshbin/magellon-angular-app ./
sudo docker run -d --restart=always --network magellon  -p 8282:80  khoshbin/magellon-angular-app 
docker run -e API_URL="http://127.0.0.1:8000/web/" -p <host-port>:<container-port> magellon-angular-app
sudo docker run -it -p8282:80  khoshbin/magellon-angular-app
`
sudo docker exec -it <container_id> bash
`docker run --rm -it -p 15672:15672 -p 5672:5672 rabbitmq:3-management`

## Docker-Compose
`sudo docker-compose build
sudo docker-compose up`


https://blog.carlesmateo.com/2022/07/20/creating-a-rabbitmq-docker-container-accessed-with-python-and-pika/

## Docker-Network
sudo docker network create magellon
docker run -d --name my-angular-container --network magellon -p 8080:80 my-angular-app
docker run -d --name my-fastapi-container --network magellon -p 8000:8000 my-fastapi-app

http://128.186.103.43:8282/view-image[config.json](compose%2Fconsul-config%2Fconfig.json)


{
"CONSUL_HOST": "192.168.92.133",
"CONSUL_PORT": "8500",
"CONSUL_USERNAME": "8500",
"CONSUL_PASSWORD": "8500",
"CONSUL_SERVICE_NAME": "magellon-core-service",
"CONSUL_SERVICE_ID": "magellon-service-" ,
"consul_config": {
"host": "192.168.92.133",
"port": 8500,
"scheme": "https",
"verify": false,
"token": "my_token",
"username": "my_username",
"password": "my_password"
},
"IMAGE_ROOT_URL": "http://localhost/cdn/",
"IMAGE_SUB_URL": "images/",
"THUMBNAILS_SUB_URL": "thumbnails/",
"FFT_SUB_URL": "FFTs/",
"IMAGE_ROOT_DIR": "/app/data",
"IMAGES_DIR": "/app/data/images/",
"FFT_DIR": "/app/data/FFTs/",
"THUMBNAILS_DIR": "/app/data/thumbnails/",
"JOBS_DIR": "/app/data/processing/",
"DB_Driver": "mysql+pymysql",
"DB_USER": "behdad",
"DB_PASSWORD": "behd1d#3454!2",
"DB_HOST": "5.161.212.237",
"DB_Port": "3306",
"DB_NAME": "magellon01"
}


rm -rf "/home/behdad/projects/Magellon/"
cd /home/behdad/projects

mkdir -p /projects
gh repo clone sstagg/Magellon
cd Magellon/CoreService/
`
sudo docker build --no-cache -f ../infrastructure/docker/Dockerfile -t khoshbin/magellon-main-service ./

sudo docker login
sudo docker push khoshbin/magellon-main-service
sudo docker run -it -p8181:80 khoshbin/magellon-main-service

sudo docker run -it -p8080:80  khoshbin/magellon-main-service bash
sudo docker run -it -p8080:80 -v /mnt/hpc_mount:/app/data khoshbin/magellon-main-service bash

sudo docker run -d --restart=always -p 8181:80 khoshbin/magellon-main-service


sudo docker run -d --restart=always  --name magellon-core-service01 --network magellon -p 8080:80 -v /mnt/hpc:/app/data  -e DATA_DIR=/app/data khoshbin/magellon-main-service

sudo ufw allow 8181

cd "/home/behdad/projects/Magellon/WebApp/"
sudo docker build --no-cache  --build-arg API_URL="http://maia.cryoem.fsu.edu:8080/web/" -f ../infrastructure/docker/angular/Dockerfile -t khoshbin/magellon-angular-app ./
sudo docker build --no-cache  --build-arg API_URL="http://magellon-core-service01:80/web/" -f ../infrastructure/docker/angular/Dockerfile -t khoshbin/magellon-angular-app ./
sudo docker build --no-cache --progress=plain  --build-arg API_URL="http://128.186.103.43:8080/web/" -f ../infrastructure/docker/angular/Dockerfile -t khoshbin/magellon-angular-app ./

sudo docker push khoshbin/magellon-angular-app

sudo docker run -it -p8282:80  khoshbin/magellon-angular-app

sudo docker run -d --restart=always --network magellon  --name magellon-angular-webapp01 -p 8181:80  khoshbin/magellon-angular-app
sudo docker run -it --network magellon  --name magellon-angular-webapp01  -p 8181:80  khoshbin/magellon-angular-app bash


sudo docker ps
sudo docker exec -it 9e4dd01b930c bash
sudo docker network create magellon
sudo docker rm 927f8670b7c4 -f

sudo docker images
sudo docker rmi -f ef1c9abbd37c


`





