variable "name_prefix" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "main_instance_id" {
  type = string
}

variable "gpu_instance_id" {
  type = string
}

variable "alb_arn_suffix" {
  type        = string
  description = "Last two path segments of the ALB ARN (used by CloudWatch dimensions)"
}

variable "target_group_arn_suffix" {
  type        = string
  description = "Last two path segments of the target group ARN"
}

variable "efs_id" {
  type = string
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
