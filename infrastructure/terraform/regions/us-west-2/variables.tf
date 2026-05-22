variable "environment" {
  type    = string
  default = "prod"
}

variable "domain_name" {
  type        = string
  description = "Apex domain. Leave empty to use the ALB's AWS DNS name over HTTP."
  default     = ""
}

variable "route53_zone_id" {
  type        = string
  description = "Route 53 hosted zone ID. Required only when domain_name is set."
  default     = ""
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "key_pair_name" {
  type    = string
  default = ""
}

variable "main_instance_type" {
  type    = string
  default = "t3.xlarge"
}

variable "gpu_instance_type" {
  type    = string
  default = "g4dn.xlarge"
}

variable "main_volume_size" {
  type    = number
  default = 100
}

variable "gpu_volume_size" {
  type    = number
  default = 80
}

variable "gpu_spot_max_price" {
  type    = string
  default = "0.20"
}

variable "cuda_image" {
  type    = string
  default = "nvidia/cuda:12.1.0-devel-ubuntu22.04"
}

variable "motioncor_binary" {
  type    = string
  default = "MotionCor2_1.6.4_Cuda121_Mar312023"
}

variable "mysql_root_password" {
  type      = string
  sensitive = true
}

variable "mysql_database" {
  type    = string
  default = "magellon01"
}

variable "mysql_user" {
  type    = string
  default = "magellon_user"
}

variable "mysql_password" {
  type      = string
  sensitive = true
}

variable "rabbitmq_user" {
  type    = string
  default = "rabbit"
}

variable "rabbitmq_password" {
  type      = string
  sensitive = true
}

variable "dragonfly_password" {
  type      = string
  sensitive = true
}

variable "grafana_user" {
  type    = string
  default = "admin"
}

variable "grafana_password" {
  type      = string
  sensitive = true
}
