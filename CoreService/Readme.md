steps to create a virtual environment inside a directory using the command[ReadMe.md](..%2Finfrastructure%2Fdocker%2FReadMe.md) line:

    Open your terminal or command prompt.
    Navigate to the directory where you want to create the virtual environment. You can use the cd command to change directories. For example: cd /path/to/directory
    Once you are in the directory, run the following command to create a new virtual environment:

`python -m venv env`

This will create a new directory called env inside your current directory that contains the virtual environment.
Note: If you have multiple versions of Python installed on your system, you may need to specify the Python version you want to use. For example, to use Python 3.8, you would run: python3.8 -m venv env

Activate the virtual environment by running the following command:

`source env/bin/activate`

This will activate the virtual environment and change your prompt to reflect that you are now working inside it.
Note: If you are using Windows, the activation command is slightly different: env\Scripts\activate
Once you've activated the virtual environment, you can install packages and work on your project without affecting the global Python installation. To exit the virtual environment, simply run the command deactivate.
rm -fr ".git/rebase-merge"
```
# we have used following command to capture requirements:
pip freeze > requirements.txt
# then to install dependencies you need to use:
pip install -r requirements.txt

python.exe -m uvicorn main:app --reload

```

`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Unrestricted
`

https://dassum.medium.com/building-rest-apis-using-fastapi-sqlalchemy-uvicorn-8a163ccf3aa1
ORMs:
https://ponyorm.org/


# Deployment

To deploy a Magellon application to a Debian 11 server, you can follow these general steps:

Install necessary dependencies:

`sudo apt-get update
sudo apt-get install -y python3-pip python3-dev build-essential libffi-dev libssl-dev`

Install uvicorn and gunicorn using pip:

_sudo pip3 install uvicorn gunicorn_

Copy your CoreService files to your Debian 11 server using SCP or any other file transfer method.

Create a virtual environment for your application:

`python3 -m venv myenv
source myenv/bin/activate`

Install your application's dependencies inside the virtual environment:

`pip3 install -r requirements.txt`

Test your application locally:

`uvicorn main:app --reload`
`uvicorn main:app --port 8080`
Once your application is running correctly, you can configure a Gunicorn systemd service file. Create a file called /etc/systemd/system/myapp.service with the following content:

```
[Unit]
Description=Gunicorn instance to serve coreservice
After=network.target

[Service]
User=yourusername
Group=www-data
WorkingDirectory=/home/yourusername/myapp
Environment="PATH=/home/yourusername/myenv/bin"
ExecStart=/home/yourusername/myenv/bin/gunicorn --workers 2 --bind unix:/home/yourusername/myapp/myapp.sock main:app

[Install]
WantedBy=multi-user.target
```

Make sure to replace yourusername with your server's username and /home/yourusername/myapp with the path to your application files.

Reload systemd and start the Gunicorn service:

`
sudo systemctl daemon-reload
sudo systemctl start myapp
sudo systemctl enable myapp
`
Test your application by accessing it through a web browser or using curl:

    curl http://localhost/

Congratulations! 


## Dependency Injection
https://python-dependency-injector.ets-labs.org/examples/application-single-container.html
https://python-dependency-injector.ets-labs.org/examples/fastapi.html
https://python-dependency-injector.ets-labs.org/examples/fastapi-sqlalchemy.html
https://kimlehtinen.com/python-flask-dependency-injection/
