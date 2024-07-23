steps to create a virtual environment inside a directory using the command[ReadMe.md](..%2Finfrastructure%2Fdocker%2FReadMe.md) line:

/gpfs/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc
/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc

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

`
python3 -m venv myenv
source myenv/bin/activate
`

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


## Prometus and Grafana
prometheus_client
https://github.com/Kludex/fastapi-prometheus-grafana
https://github.com/Blueswen/fastapi-observability



Components:
https://github.com/Lattice-Automation/seqviz
https://npm.io/package/alignment.js
https://github.com/veg/phylotree.js
https://npm.io/package/igv
https://npm.io/package/pileup
https://www.canvasxpress.org
https://npm.io/package/lexicon-mono-seq

https://npm.io/package/vue-svg-msa

https://npm.io/package/ntseq
https://npm.io/package/static-interval-tree
https://npm.io/package/dna
https://npm.io/package/bionode-seq
https://www.bionode.io/


ssh -N -L 3310:kriosdb.rcc.fsu.edu:3306 bk2n@hpc-login.rcc.fsu.edu
hpc-login.rcc.fsu.edu
maia.cryoem.fsu.edu
sshfs bk22n@hpc-login.rcc.fsu.edu:/gpfs /rcc_gpfs


```WITH RECURSIVE image_hierarchy AS (
-- Anchor member: get the initial level (level 0)
SELECT oid, name, parent_id, 0 AS level
FROM image
WHERE parent_id IS NULL

    UNION ALL
    
    -- Recursive member: traverse the hierarchy based on the specified level number
    SELECT c.oid, c.name, c.parent_id, h.level + 1
    FROM image AS c
    JOIN image_hierarchy AS h ON c.parent_id = h.oid
    WHERE h.level < :level_number -- Specify the desired level number
)
SELECT parent.oid AS parent_oid, parent.name AS parent_name, COUNT(child.oid) AS num_images
FROM image_hierarchy AS child
JOIN image_hierarchy AS parent ON child.parent_id = parent.oid
WHERE child.level = :level_number - 1 -- Specify the level of the children (one level below the parent)
GROUP BY parent.oid, parent.name
HAVING COUNT(child.oid) >= :num_images -- Specify the minimum number of images
ORDER BY parent.oid;```



WITH RECURSIVE cte AS (
    -- Anchor query: Set level 0 for root images
    SELECT oid, parent_id, 0 AS level
    FROM image
    WHERE parent_id IS NULL
    UNION ALL
    -- Recursive query: Update level for child images
    SELECT i.oid, i.parent_id, cte.level + 1
    FROM image AS i
    JOIN cte ON i.parent_id = cte.oid
)
UPDATE image AS t
JOIN cte ON t.oid = cte.oid
SET t.level = cte.level;



./MotionCor3 -InMrc 23oct13a_a_00038gr_00001sq_v02_00005hl_00002ex.tif -OutMrc outImg.mrc -kV 300 -Cs 2.7 -PixSize 0.93 FmDose 0.6 -Gain ./K3-20310049.mrc

```

1.Create MagellonSDK
2.Pass Environment Variables
3.Service Discovery
4.


## Installation 1
pip freeze > requirements.txt
pip download -r requirements.txt --no-binary :all:
pip install --no-index --find-links=/path/to/local/directory -r requirements.txt

## Installation 2
pip download -r requirements.txt -d /path/to/wheelhouse
pip install --no-index --find-links=/path/to/wheelhouse -r requirements.txt

pip download --only-binary=:all: --platform manylinux1_x86_64,win_amd64,macosx_10_15_x86_64 -r requirements.txt -d /path/to/wheelhouse

    --only-binary=:all:: Instructs pip to consider all platforms when looking for pre-built binary distributions (wheels).
    --platform manylinux1_x86_64,win_amd64,macosx_10_15_x86_64: Specifies the platforms for which to download wheels. In this example, it includes Linux (manylinux1_x86_64), Windows (win_amd64), and macOS (macosx_10_15_x86_64). You can customize the platform list based on your requirements.



{
    "session_name": "22apr01a",
    "magellon_project_name": "Leginon",
    "magellon_session_name": "22apr01a",
    "camera_directory": "/gpfs",
    "copy_images": false,
    "retries": 0,
    "leginon_mysql_user": "usr_object",
    "leginon_mysql_pass": "ThPHMn3m39Ds",
    "leginon_mysql_host": "localhost",
    "leginon_mysql_port": 3310,
    "leginon_mysql_db": "dbemdata",
    "replace_type": "standard",
    "replace_pattern": "/gpfs",
    "replace_with": "Y:\\"
}

sshfs.exe bk22n@hpc-login.rcc.fsu.edu:/gpfs X:

SiriKali
bk22n@hpc-login.rcc.fsu.edu:/gpfs


{
    "session_name": "24mar25a",
    "magellon_project_name": "Leginon",
    "magellon_session_name": "24mar25a",
    "camera_directory": "/gpfs",
    "copy_images": false,
    "retries": 0,
    "leginon_mysql_user": "usr_object",
    "leginon_mysql_pass": "ThPHMn3m39Ds",
    "leginon_mysql_host": "localhost",
    "leginon_mysql_port": 3310,
    "leginon_mysql_db": "dbemdata",
    "replace_type": "standard",
    "replace_pattern": "/gpfs",
    "replace_with": "Y:\\"
}