##############################################################################
# us-west-2  –  SECONDARY (failover) region
# Identical module wiring to us-east-1 but different CIDR space (10.1.x.x)
# and a different AZ list.  Route 53 health-check failover routes traffic
# here automatically if the primary ALB goes unhealthy.
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
    key          = "magellon/us-west-2/terraform.tfstate"
    region       = "us-east-1"   # state bucket stays in primary region
    encrypt      = true
    use_lockfile = true   # S3 native locking — no DynamoDB required
  }
}

provider "aws" {
  region = "us-west-2"

  default_tags {
    tags = {
      Project     = "magellon"
      Environment = var.environment
      Region      = "us-west-2"
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name_prefix = "magellon-${var.environment}-usw2"

  tags = {
    Project     = "magellon"
    Environment = var.environment
    Region      = "us-west-2"
    ManagedBy   = "terraform"
  }
}

# ── VPC ───────────────────────────────────────────────────────────────────────
module "vpc" {
  source = "../../modules/vpc"

  name_prefix          = local.name_prefix
  vpc_cidr             = "10.1.0.0/16"      # non-overlapping with us-east-1
  azs                  = ["us-west-2a", "us-west-2b"]
  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs = ["10.1.10.0/24", "10.1.11.0/24"]
  tags                 = local.tags
}

module "iam" {
  source      = "../../modules/iam"
  name_prefix = local.name_prefix
  tags        = local.tags
}

module "efs" {
  source = "../../modules/efs"

  name_prefix          = local.name_prefix
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  private_subnet_cidrs = ["10.1.10.0/24", "10.1.11.0/24"]
  tags                 = local.tags
}

module "ec2_stack" {
  source = "../../modules/ec2_stack"

  name_prefix           = local.name_prefix
  aws_region            = "us-west-2"
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

module "alb" {
  source = "../../modules/alb"

  name_prefix                = local.name_prefix
  vpc_id                     = module.vpc.vpc_id
  public_subnet_ids          = module.vpc.public_subnet_ids
  domain_name                = var.domain_name
  route53_zone_id            = var.route53_zone_id
  main_instance_id           = module.ec2_stack.main_instance_id
  frontend_port              = 8080
  enable_deletion_protection = var.environment == "prod"
  tags                       = local.tags
}

module "monitoring" {
  source = "../../modules/monitoring"

  name_prefix             = local.name_prefix
  aws_region              = "us-west-2"
  main_instance_id        = module.ec2_stack.main_instance_id
  gpu_instance_id         = module.ec2_stack.gpu_spot_request_id
  alb_arn_suffix          = regex("loadbalancer/(.*)", module.alb.alb_arn)[0]
  target_group_arn_suffix = regex("targetgroup/(.*)", module.alb.target_group_arn)[0]
  efs_id                  = module.efs.efs_id
  alert_email             = var.alert_email
  tags                    = local.tags
}
