# Magellon
Repository for Magellon cryo-EM data collection and processing code

## Dependencies
to capture dependencies run:

```shell
# we have used following command to capture requirements:
pip freeze > requirements.txt
# then to install dependencies you need to use:
pip install -r requirements.txt
```

### PyLint
```shell
#  output any errors or warnings according to the configuration in your .pylintrc file
pylint --load-plugins pylint_flask  app.py

```
### PyTest
```shell
#  run unit tests
pytest tests/

```


# Documentation
for documentation please refer to https://docs.magellon.org

for a demo of api please go to :
https://api.magellon.org/openapi

## Installation

### Docker Installation
Make sure that you have the appropriate permissions to run the scripts. You may need to use sudo to run the scripts as root.

Download the install-mysql.sh script to your system.
Open a terminal and navigate to the directory where you downloaded the install-mysql.sh script.
Make the script executable by running the following command:

`chmod +x install-mysql.sh`

Run the install-mysql.sh script by running the following command:

`./install-mysql.sh`

This will install MySQL on your system.
Download the install-docker.sh script to your system.
Open a terminal and navigate to the directory where you downloaded the install-docker.sh script.
Make the script executable by running the following command:

`chmod +x install-docker.sh`

Run the install-docker.sh script by running the following command:

`./install-docker.sh`

This will install Docker on your system.
Note that these scripts may require additional configuration depending on your specific use case. It is important to read the documentation for each script and ensure that it is appropriate for your system before running them.