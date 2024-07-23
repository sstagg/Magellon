
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
nvm install latest
nvm install v20.15.1
node --version

sudo apt install ca-certificates curl gnupg
sudo apt update && sudo apt install github-desktop

bash Anaconda3-2024.06-1-Linux-x86_64.sh

sudo apt-get install ./docker-desktop-amd64.deb
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
sudo systemctl --user start docker-desktop

sudo docker volume create portainer_data

sudo mkdir /rcc_gpfs
sudo chmod -R 777 /rcc_gpfs

sudo apt install python3.12-venv
sudo apt-get install python3-dev

ssh -N -L 3310:kriosdb.rcc.fsu.edu:3306 bk2n@hpc-login.rcc.fsu.edu
sshfs bk22n@hpc-login.rcc.fsu.edu:/gpfs /rcc_gpfs

Sessios to test:
14210 14228 14232 14211 14204
24jun28a 24jul02a 24jul03a 24jul17a 24jul23b




{
    "session_name": "24jun28a",
    "magellon_project_name": "Leginon",
    "magellon_session_name": "24jun28a",
    "camera_directory": "/rcc_gpfs",
    "copy_images": false,
    "retries": 0,
    "leginon_mysql_user": "usr_object",
    "leginon_mysql_pass": "ThPHMn3m39Ds",
    "leginon_mysql_host": "localhost",
    "leginon_mysql_port": 3310,
    "leginon_mysql_db": "dbemdata",
    "replace_type": "standard",
    "replace_pattern": "/gpfs",
    "replace_with": "/rcc_gpfs"
}




sshfs.exe bk22n@hpc-login.rcc.fsu.edu:/gpfs X:

SiriKali
bk22n@hpc-login.rcc.fsu.edu:/gpfs