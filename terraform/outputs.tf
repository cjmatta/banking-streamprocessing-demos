output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.dev_instance.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_eip.dev_eip.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.dev_instance.private_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.dev_instance.public_dns
}

output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.dev_sg.id
}

output "ssh_connection_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_eip.dev_eip.public_ip}"
}

output "development_ports" {
  description = "Development ports that are open"
  value = {
    ssh     = 22
    http    = 8000
    alt_http = 8080
    react   = 3000
    flask   = 5000
  }
}

output "elastic_ip" {
  description = "Elastic IP address attached to the instance"
  value       = aws_eip.dev_eip.public_ip
} 