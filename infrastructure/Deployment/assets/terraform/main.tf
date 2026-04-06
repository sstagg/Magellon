
provider "hcloud" {                # Provider designation hetzner
  token = "${var.hcloud_token}"      # The token for connection to the hetzner API is specified in the terraform.tfvars file
}

# Resource random to generate random characters
resource "random_string" "name" {
  length = 6
  special = false
  upper = false
}

# The designation of the name, which is built from the variable name + environment terraform + result random
locals {
  name = "${var.name}-${terraform.workspace}-${random_string.name.result}"
}