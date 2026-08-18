# variables.tf

variable "region" {
  description = "The AWS region to deploy the resources"
  type        = string
  default     = "us-east-1" # US East (N. Virginia)
}

variable "ami_id" {
  description = "The AMI ID for the EC2 instance"
  type        = string
  default     = "ami-053b12d3152c0cc71"  # Ubuntu , x86 Arch
}

variable "instance_type" {
  description = "The EC2 instance type"
  type        = string
  default     = "t2.micro"  # Default instance type
}
