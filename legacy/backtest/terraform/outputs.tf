output "ec2_instance_id" {
  description = "The ID of the EC2 instance"
  value       = aws_instance.gitops_server.id
}

output "ec2_instance_public_ip" {
  description = "The public IP address of the EC2 instance"
  value       = aws_instance.gitops_server.public_ip
}