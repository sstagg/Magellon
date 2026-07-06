# Credentials come from the standard AWS credential chain
# (AWS_PROFILE / AWS_ACCESS_KEY_ID env vars / ~/.aws/credentials).
# Never inline keys here — a real key pair was committed in this file
# once and had to be revoked.
provider "aws" {
  region = "us-east-1"
}

#Create two web servers
resource "aws_instance" "webserver" {
  count = 2
  ami = "ami-0323c3dd2da7fb37d"
  instance_type = "t2.micro"
  tags = {
    Name = "MyWebServer"
  }
}

#Create one db server
resource "aws_instance" "dbserver" {
  count = 1
  ami = "ami-0323c3dd2da7fb37d"
  instance_type = "t2.micro"
  tags = {
    Name = "MyDBServer"
  }
}
# Generate inventory file
resource "local_file" "inventory" {
  filename = "./ansible/hosts.ini"
  content = <<EOF
  [webserver]
  ${aws_instance.webserver[0].public_ip}
  ${aws_instance.webserver[1].public_ip}
  [dbserver]
  ${aws_instance.dbserver[0].public_ip}
EOF
}