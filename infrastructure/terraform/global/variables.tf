variable "domain_name" {
  type        = string
  description = "Apex domain e.g. magellon.org. Leave empty to skip Route 53 zone creation."
  default     = ""   # empty = no Route 53 resources created
}

variable "primary_alb_dns" {
  type    = string
  default = ""
}

variable "primary_alb_zone_id" {
  type    = string
  default = ""
}

variable "secondary_alb_dns" {
  type    = string
  default = ""
}

variable "secondary_alb_zone_id" {
  type    = string
  default = ""
}
