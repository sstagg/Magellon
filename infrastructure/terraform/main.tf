# This file is intentionally minimal.
# The production deployment is fully modular – see:
#
#   modules/vpc/           VPC, subnets, NAT gateways, VPC flow logs
#   modules/iam/           EC2 instance role (SSM, ECR, Secrets Manager, CloudWatch)
#   modules/efs/           Shared EFS storage (magellon/gpfs/jobs)
#   modules/alb/           ALB, HTTPS, WAF v2, ACM certificate
#   modules/ec2_stack/     Security groups, main CPU instance, GPU spot instance
#   modules/monitoring/    CloudWatch alarms, SNS, dashboard
#
#   regions/us-east-1/    PRIMARY region – deploy here first
#   regions/us-west-2/    SECONDARY (failover) region
#   global/               Route53 hosted zone + health-check failover records
#
# Deployment order:
#   1. cd global/          && terraform init && terraform apply
#   2. Delegate NS records at your registrar
#   3. cd regions/us-east-1 && terraform init && terraform apply
#   4. cd regions/us-west-2 && terraform init && terraform apply
#   5. cd global/           && terraform apply  (add ALB DNS values from step 3+4)
