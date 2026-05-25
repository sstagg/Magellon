output "alb_arn"          { value = aws_lb.this.arn }
output "alb_dns_name"     { value = aws_lb.this.dns_name }
output "alb_zone_id"      { value = aws_lb.this.zone_id }
output "alb_sg_id"        { value = aws_security_group.alb.id }
output "target_group_arn" { value = aws_lb_target_group.frontend.arn }
output "certificate_arn"  { value = local.has_domain ? aws_acm_certificate.this[0].arn : "" }
output "waf_acl_arn"      { value = aws_wafv2_web_acl.this.arn }

# Ready-to-use URL — no thinking required
output "app_url" {
  description = "URL to access the application (HTTP until domain_name is set)"
  value       = local.has_domain ? "https://${var.domain_name}" : "http://${aws_lb.this.dns_name}"
}
