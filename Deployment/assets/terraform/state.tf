#terraform {
#  backend "s3" {                          # Backend designation
#  bucket = "foo-terraform"                # Bucket name
#  key = "bucket/terraform.tfstate"        # Key
#  region = "us-east-1"                    # Region
#  encrypt = "true"                        # Encryption enabled
#  }
#}
terraform {
  required_providers {
    hcloud = {
      source = "hetznercloud/hcloud"
    }
  }
}