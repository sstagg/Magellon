variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "domain_name" {
  description = "Apex domain (e.g. magellon.org). Leave empty to use the ALB's default AWS DNS name over HTTP."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID. Required only when domain_name is set."
  type        = string
  default     = ""
}

variable "main_instance_id" {
  type = string
}

variable "frontend_port" {
  type    = number
  default = 8080
}

variable "enable_deletion_protection" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
