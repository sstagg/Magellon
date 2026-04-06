# DevOps Project

This project uses Vagrant to provision four Debian 11 virtual machines, each with a different service installed: MySQL, RabbitMQ, a Flask app, and an Angular app. It also includes a fifth machine for Prometheus monitoring.
Prerequisites

Before running this project, you will need to have the following software installed on your local machine:

    Vagrant
    VirtualBox

## Getting Started

To get started, clone this repository to your local machine:

`git clone https://github.com/sstagg/Magellon`

Then, navigate to the project directory and start the virtual machines using Vagrant:


```bash
cd Magellon
vagrant up
```

This will provision the virtual machines according to the specifications in the Vagrantfile.
Accessing the Virtual Machines

Each virtual machine is accessible via SSH using the private IP address assigned in the Vagrantfile. Here are the IP addresses for each machine:

    MySQL: 192.168.1.101
    RabbitMQ: 192.168.1.102
    Flask app: 192.168.1.103
    Angular app: 192.168.1.104
    Prometheus: 192.168.1.105

To access a machine via SSH, use the vagrant ssh command followed by the name of the machine. For example:

`vagrant ssh mysql`

This will log you in to the MySQL machine via SSH.


## Running the Services

Once the virtual machines are provisioned, you can access the services by visiting the appropriate URL in your web browser:

    MySQL: http://192.168.1.101
    RabbitMQ: http://192.168.1.102:15672
    Flask app: http://192.168.1.103:5000
    Angular app: http://192.168.1.104:4200
    Prometheus:



    https://www.taniarascia.com/what-are-vagrant-and-virtualbox-and-how-do-i-use-them/

vagrant box add ubuntu/trusty64
vagrant init ubuntu/trusty64
vagrant up
vagrant halt
vagrant plugin install vagrant-vbguest
vagrant ssh