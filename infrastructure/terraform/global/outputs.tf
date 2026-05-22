output "tf_state_bucket" {
  value = aws_s3_bucket.tf_state.bucket
}

output "hosted_zone_id" {
  value = local.create_zone ? aws_route53_zone.main[0].zone_id : "not created (domain_name is empty)"
}

output "name_servers" {
  value = local.create_zone ? aws_route53_zone.main[0].name_servers : []
}
