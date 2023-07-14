# Token Variable Definition
variable "hcloud_token" {
  default = "mzpz2c6RZGt2AVqTa4MfcnSEi31x9atkIYVsyUbNe882q7bJqc1zuVv8wLSpJ9Gs"
}

# Name variable definition
variable "name" {
  default = "Behdad"
}

# Defining a variable source OS image for an instance
variable "image" {
  default = "debian-11"
}

# Definition of an instance type variable depending on the choice of tariff
variable "server_type" {
  default = "cpx11"
}
# Definition of the region in which the instance will be created
variable "location" {
  default = "ash" #"nbg1"
}

# Determining the ssh key that will be added to the instance when creating
variable "public_key" {
  default = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDiNC5WM8UrhqzrfrGCoCvAKraPigp3iKJeKvM1izQfaOHtR2JA/PUtdRI1YVU+KqIxyGJ+q6h7Xmw9Z1GS3R95aBoWShmzGuL33t0fV61kCJSoFRPNlCSVwZUVvUK8AQ4HPKhfx2E41zh1VB+Cn4wez78rVGNmS2jol8cP7jb4Gmq27uMp+YtnMl7BcWvnSLE8sFkjvMLoXz0TsMe2Wq9QsCZCTUZYwSuEyM9Qt2+VZMW+fTbyZeikJvY6YXtmLaHDALY1LZDMMv3Ow+2+3vlMbXT5HIhBCh+/bHf0jpfXey6M4hQVzykSsa90w9AXqySig1V8PKGVytxk4RbQMfghe7tNnzpGQYYJOjGOf0HB2JOx7MkvHIHyqJRDsezn68rrgXHfsa4BX9yGUaSvX8xvvVoXhora6cen8eX3CfLbFrAuO4IXgllQ6G2JLtpAXfYPCuIoh/2ISvJgP+P5lZs/H5mChAaGPcWKICnOfCztzutGSjzqLH3Hl3l7q3ZTT38= behdad@behdad-pc"
}

# Obtain ssh key data
#data "hcloud_ssh_key" "ssh_key" {
#  fingerprint = "30:d2:75:a7:88:3e:5b:4f:b6:48:13:8f:55:cb:49:f8"
#}