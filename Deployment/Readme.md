

cd Magellon/Deployment/


### Preparing Installation:
#### Install Python in the installation computer
#### Install Requirements in the installation computer

### Installation Process:
#### Install Python in the target server
#### Install git in the target server
#### Install MySql in the target server if required
#### Install MySql Database in the target server if required


#### Install docker engine in the target server
#### Install clone code from git in the target server
#### build core service docker image in the target server
#### build webapp docker image in the target server
#### run core service container in the target server
#### run webapp container in the target server
#### Configure firewall for the target server


```

cd Magellon/Deployment/
chmod +x install_and_run.sh  # Make the script executable
./install_and_run.sh


```

nuitka --standalone main.py
pip install pydantic==2.0.3
pip show pydantic
pip show nuitka

https://www.infoworld.com/article/3673932/intro-to-nuitka-a-better-way-to-compile-and-distribute-python-applications.html
nuitka --follow-imports --include-plugin-directory=mods main.py



https://github.com/sickcodes/Docker-OSX
https://checkout.macincloud.com/
https://aws.amazon.com/ec2/instance-types/mac/


`
ssh-keygen -F 5.161.91.240
ssh-keygen -R 5.161.91.240
ssh-keyscan -H 5.161.91.240 >> ~/.ssh/known_hosts

ansible-playbook ./playbooks/mysql.yml -i ./playbooks/inventory.ini
ansible-playbook ./playbooks/docker.yaml -i ./playbooks/inventory.ini


textual run main.py --dev
`
