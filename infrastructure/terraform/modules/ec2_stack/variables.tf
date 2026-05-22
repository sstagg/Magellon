variable "name_prefix" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "alb_sg_id" {
  type        = string
  description = "ALB security group ID – only it can reach the frontend port"
}

variable "instance_profile_name" {
  type = string
}

variable "efs_id" {
  type = string
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

variable "frontend_port" {
  type    = number
  default = 8080
}

variable "gpu_spot_max_price" {
  type    = string
  default = "0.20"
}

variable "key_pair_name" {
  type    = string
  default = ""
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
  type = string
}

variable "mysql_user" {
  type = string
}

variable "mysql_password" {
  type      = string
  sensitive = true
}

variable "rabbitmq_user" {
  type = string
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
  type = string
}

variable "grafana_password" {
  type      = string
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
