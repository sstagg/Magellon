output "vpc_id"          { value = module.vpc.vpc_id }
output "alb_dns_name"    { value = module.alb.alb_dns_name }
output "alb_zone_id"     { value = module.alb.alb_zone_id }
output "main_private_ip" { value = module.ec2_stack.main_private_ip }
output "efs_id"          { value = module.efs.efs_id }
