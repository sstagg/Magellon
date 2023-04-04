steps to create a virtual environment inside a directory using the command line:

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

```
# we have used following command to capture requirements:
pip freeze > requirements.txt
# then to install dependencies you need to use:
pip install -r requirements.txt

python flask -m run
```


https://dassum.medium.com/building-rest-apis-using-fastapi-sqlalchemy-uvicorn-8a163ccf3aa1
ORMs:
https://ponyorm.org/