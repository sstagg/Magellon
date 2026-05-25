variable "name_prefix" {
  description = "Prefix applied to every resource name (e.g. magellon-prod-use1)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "azs" {
  description = "List of availability zones to use (must match subnet lists)"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDRs for public subnets, one per AZ"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDRs for private subnets, one per AZ"
  type        = list(string)
}

variable "tags" {
  description = "Tags merged onto every resource"
  type        = map(string)
  default     = {}
}
