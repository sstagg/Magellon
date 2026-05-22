##############################################################################
# us-east-1  –  PRIMARY region
# Wires all modules together.  All resources are private except the ALB.
##############################################################################

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket       = "magellon-terraform-state"
    key          = "magellon/us-east-1/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true   # S3 native locking — no DynamoDB required
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "magellon"
      Environment = var.environment
      Region      = "us-east-1"
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name_prefix = "magellon-${var.environment}-use1"

  tags = {
    Project     = "magellon"
    Environment = var.environment
    Region      = "us-east-1"
    ManagedBy   = "terraform"
  }
}

# ── VPC ───────────────────────────────────────────────────────────────────────
module "vpc" {
  source = "../../modules/vpc"

  name_prefix          = local.name_prefix
  vpc_cidr             = "10.0.0.0/16"
  azs                  = ["us-east-1a", "us-east-1b"]
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  tags                 = local.tags
}

# ── IAM ───────────────────────────────────────────────────────────────────────
module "iam" {
  source      = "../../modules/iam"
  name_prefix = local.name_prefix
  tags        = local.tags
}

# ── EFS ───────────────────────────────────────────────────────────────────────
module "efs" {
  source = "../../modules/efs"

  name_prefix          = local.name_prefix
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  tags                 = local.tags
}

# ── EC2 Stack ─────────────────────────────────────────────────────────────────
module "ec2_stack" {
  source = "../../modules/ec2_stack"

  name_prefix           = local.name_prefix
  aws_region            = "us-east-1"
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  alb_sg_id             = module.alb.alb_sg_id
  instance_profile_name = module.iam.instance_profile_name
  efs_id                = module.efs.efs_id

  main_instance_type = var.main_instance_type
  gpu_instance_type  = var.gpu_instance_type
  main_volume_size   = var.main_volume_size
  gpu_volume_size    = var.gpu_volume_size
  gpu_spot_max_price = var.gpu_spot_max_price
  key_pair_name      = var.key_pair_name
  cuda_image         = var.cuda_image
  motioncor_binary   = var.motioncor_binary

  mysql_root_password = var.mysql_root_password
  mysql_database      = var.mysql_database
  mysql_user          = var.mysql_user
  mysql_password      = var.mysql_password
  rabbitmq_user       = var.rabbitmq_user
  rabbitmq_password   = var.rabbitmq_password
  dragonfly_password  = var.dragonfly_password
  grafana_user        = var.grafana_user
  grafana_password    = var.grafana_password

  tags = local.tags
}

# ── ALB ───────────────────────────────────────────────────────────────────────
# ALB depends on main_instance_id so it must come AFTER ec2_stack.
module "alb" {
  source = "../../modules/alb"

  name_prefix               = local.name_prefix
  vpc_id                    = module.vpc.vpc_id
  public_subnet_ids         = module.vpc.public_subnet_ids
  domain_name               = var.domain_name
  route53_zone_id           = var.route53_zone_id
  main_instance_id          = module.ec2_stack.main_instance_id
  frontend_port             = 8080
  enable_deletion_protection = var.environment == "prod"
  tags                      = local.tags
}

# ── Monitoring ────────────────────────────────────────────────────────────────
module "monitoring" {
  source = "../../modules/monitoring"

  name_prefix            = local.name_prefix
  aws_region             = "us-east-1"
  main_instance_id       = module.ec2_stack.main_instance_id
  gpu_instance_id        = module.ec2_stack.gpu_spot_request_id  # spot instance ID
  alb_arn_suffix         = regex("loadbalancer/(.*)", module.alb.alb_arn)[0]
  target_group_arn_suffix = regex("targetgroup/(.*)", module.alb.target_group_arn)[0]
  efs_id                 = module.efs.efs_id
  alert_email            = var.alert_email
  tags                   = local.tags
}
