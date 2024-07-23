
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