ssh-keygen -f "/home/behdad/.ssh/known_hosts" -R "5.161.182.12"


ssh root@5.161.182.12























https://medium.com/@rajeshshukla_49087/ansible-inventory-file-using-terraform-b305db3ead2

https://maddevs.io/blog/terraform-hetzner/
https://computingforgeeks.com/deploy-vm-instances-on-hetzner-cloud-with-terraform/

https://stackoverflow.com/questions/49743220/how-do-i-create-an-ssh-key-in-terraform
30:d2:75:a7:88:3e:5b:4f:b6:48:13:8f:55:cb:49:f8

17  sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
18  wget -O- https://apt.releases.hashicorp.com/gpg | \\n    gpg --dearmor | \\n    sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg\n
19  gpg --no-default-keyring \\n    --keyring /usr/share/keyrings/hashicorp-archive-keyring.gpg \\n    --fingerprint\n
20  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \\n    https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \\n    sudo tee /etc/apt/sources.list.d/hashicorp.list\n
21  sudo apt update
22  sudo apt-get install terraform

git clone https://x-token-auth:ygl774GahlOqDdybWHKS@bitbucket.org/fyton/phaeton-spring-api.git
https://x-token-auth@bitbucket.org/fyton/phaeton-spring-api.git
ygl774GahlOqDdybWHKS


ssh-keygen -q -N ""
xclip -sel clip ~/.ssh/id_rsa.pub


## Commands
e
terraform init       # Config Initialization
terraform plan       # Action check
terraform apply -input=false -auto-approve     # Launch action
terraform destroy      # Destroy action