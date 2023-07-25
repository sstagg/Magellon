
# Magellon Main Service

This is a  Flask application that demonstrates how to build a web application using the Flask framework.
## Getting Started

To get started with this application, you'll need to follow these steps:

    Install Python 3.7 or later on your system.
    Clone this repository to your local machine.
    Install the required Python packages by running pip install -r requirements.txt.
    Install Cuda Toolkit for windows: https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda_12.1.0_531.14_windows.exe
    Run the Flask development server by executing flask run from the command line.
    Open your web browser and navigate to http://localhost:5000 to view the application.

`gh repo clone sstagg/Magellon`

## Project Structure[mariadb.md](..%2Finfrastructure%2Fmanual%2Fmariadb.md)

This project follows the recommended Flask project structure, with the following directories:

    app.py: This file contains the main application code.
    config.py: This file contains the application configuration settings.
    helpers.py: This file contains helper functions used throughout the application.
    models: This directory contains the database models for the application.
    views: This directory contains the Flask views (routes) for the application.
    templates/: This directory contains the Jinja2 templates used to render HTML pages.
    static/: This directory contains static files such as CSS and JavaScript.
    data/: This directory contains data files used by the application.

# References
https://www.l3harrisgeospatial.com/docs/backgroundfastfouriertransform.html

## Conventions and Guidelines

This project follows the following naming conventions and guidelines:
    

    Variables: Use lowercase letters and underscores to separate words. For example: my_variable, another_variable, some_list.
    Functions: Use lowercase letters and underscores to separate words. For example: my_function, calculate_sum, print_message.
    Classes: Use CamelCase starting with an uppercase letter. For example: MyClass, MyOtherClass, MySuperCoolClass.
    File names: Use lowercase letters and underscores to separate words. For example: my_module.py, my_script.py, my_package/__init__.py.

In addition to these conventions, it's also recommended to use descriptive names that indicate the purpose of the variable, function, class, or file. This helps make your code more self-explanatory and easier to understand.
Contributing

### Contributions
Contributions to this project are welcome! If you have any suggestions or find any bugs, please open an issue or submit a pull request.

### License

This project is licensed under the MIT License. See the LICENSE file for details.

http://127.0.0.1:5000/math/1/3/add


## Tasks:
Connection to new magellon database
Add Airflow
Add frameTransfer, fft , ctf estimation
get 


`
pip install mysqlclient
pip install sqlacodegen
sqlacodegen mysql://admin:pass@192.168.92.133:3306/magellon03 --outfile sqlalchemy_models2.py
`

sqlacodegen mysql://behdad:behd1d#3454!2@5.161.212.237:3306/magellon01 --outfile sqlalchemy_models2.py

ssh -N -L 3310:kriosdb.rcc.fsu.edu:3306 bk22n@hpc-login.rcc.fsu.edu


{
"job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
"magellon_project_name": "Leginon",
"magellon_session_name": "23jun14a",
"target_directory": "C:/temp/target2",
"camera_directory": "C:/temp/frames",
"leginon_mysql_user": "usr_object",
"leginon_mysql_pass": "ThPHMn3m39Ds",
"leginon_mysql_host": "kriosdb.rcc.fsu.edu",
"leginon_mysql_port": 3306,
"leginon_mysql_db": "dbemdata",
"session_name": "23jun14a"
}

{
"session_name": "22apr01a",
"magellon_project_name": "Leginon",
"magellon_session_name": "22apr01a",
"camera_directory": "/gpfs",
"copy_images": true,
"retries": 0,
"leginon_mysql_user": "usr_object",
"leginon_mysql_pass": "ThPHMn3m39Ds",
"leginon_mysql_host": "kriosdb.rcc.fsu.edu",
"leginon_mysql_port": 3306,
"leginon_mysql_db": "dbemdata"
}


mysql -h kriosdb.rcc.fsu.edu -u usr_object -p

dose = dose*(10**-20)*exposure_time/preset_exposure_time


{
cameras {
edges {
node {
Oid
name

      }
    }
}
}


{
sessions {
edges {
node {
sessionId: Oid
sessionName: name
project : project.name
}
}
}
}


{
sessions {
edges {
node {
sessionId: Oid
sessionName: name
project {
name
}
images{
edges{
node{
Oid
Name
}
}
}

      }
    }
}
}



mutation {
createProject(projectData: {name: "New Project", description: "Project description"}) {
project {
id
name
description
}
}
}
