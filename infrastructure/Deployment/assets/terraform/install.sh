#!/bin/bash

terraform init
terraform plan
terraform apply -input=false -auto-approve