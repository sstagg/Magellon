##############################################################################
# Global Resources — deploy ONCE before the region stacks.
#
# Creates:
#   - S3 bucket for Terraform remote state (versioned, encrypted)
#   - S3 native state locking (use_lockfile = true, no DynamoDB needed)
#
# Route 53 hosted zone and failover records are created here only when
# you have a real domain AND the IAM permissions for Route 53.
# Skip those for now and come back later.
#
# Deploy order:
#   1. cd global/              && terraform apply   ← you are here
#   2. cd regions/us-east-1/   && terraform apply
#   3. cd regions/us-west-2/   && terraform apply
#   4. (Optional, needs domain) cd global/ && terraform apply with ALB values
##############################################################################

terraform {
  required_version = ">= 1.10"   # S3 native locking requires 1.10+
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Uncomment AFTER first apply (state bucket must exist first):
  # backend "s3" {
  #   bucket       = "magellon-terraform-state"
  #   key          = "magellon/global/terraform.tfstate"
  #   region       = "us-east-1"
  #   encrypt      = true
  #   use_lockfile = true   # S3 native locking — no DynamoDB required
  # }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = {
      Project   = "magellon"
      ManagedBy = "terraform"
      Scope     = "global"
    }
  }
}

# ── S3 Terraform State Bucket ─────────────────────────────────────────────────
resource "aws_s3_bucket" "tf_state" {
  bucket        = "magellon-terraform-state"
  force_destroy = false
  tags          = { Name = "magellon-terraform-state" }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Route 53 (optional — only when domain + permissions are available) ────────
# All Route 53 resources below are skipped when primary_alb_dns is empty.

locals {
  has_primary   = var.primary_alb_dns != "" && var.primary_alb_zone_id != ""
  has_secondary = var.secondary_alb_dns != "" && var.secondary_alb_zone_id != ""
  has_failover  = local.has_primary && local.has_secondary
  create_zone   = var.domain_name != ""
}

resource "aws_route53_zone" "main" {
  count = local.create_zone ? 1 : 0
  name  = var.domain_name
  tags  = { Name = "magellon-zone" }
}

resource "aws_route53_health_check" "primary" {
  count             = local.has_primary ? 1 : 0
  fqdn              = var.primary_alb_dns
  port              = 443
  type              = "HTTPS"
  resource_path     = "/"
  failure_threshold = 3
  request_interval  = 30
  tags              = { Name = "magellon-hc-primary-use1" }
}

resource "aws_route53_health_check" "secondary" {
  count             = local.has_secondary ? 1 : 0
  fqdn              = var.secondary_alb_dns
  port              = 443
  type              = "HTTPS"
  resource_path     = "/"
  failure_threshold = 3
  request_interval  = 30
  tags              = { Name = "magellon-hc-secondary-usw2" }
}

resource "aws_route53_record" "primary" {
  count   = local.has_failover ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "PRIMARY"
  }

  set_identifier  = "primary-use1"
  health_check_id = aws_route53_health_check.primary[0].id

  alias {
    name                   = var.primary_alb_dns
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "secondary" {
  count   = local.has_failover ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"

  failover_routing_policy {
    type = "SECONDARY"
  }

  set_identifier = "secondary-usw2"

  alias {
    name                   = var.secondary_alb_dns
    zone_id                = var.secondary_alb_zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "www" {
  count   = local.has_primary ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = var.primary_alb_dns
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }
}
