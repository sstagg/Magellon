output "vpc_id"              { value = module.vpc.vpc_id }
output "alb_dns_name"        { value = module.alb.alb_dns_name }
output "alb_zone_id"         { value = module.alb.alb_zone_id }
output "main_private_ip"     { value = module.ec2_stack.main_private_ip }
output "efs_id"              { value = module.efs.efs_id }
output "dashboard_name"      { value = module.monitoring.dashboard_name }
output "sns_topic_arn"       { value = module.monitoring.sns_topic_arn }
output "app_secret_arn"      { value = module.ec2_stack.app_secret_arn }
