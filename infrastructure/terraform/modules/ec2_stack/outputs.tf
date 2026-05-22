output "main_instance_id"         { value = aws_instance.main.id }
output "main_private_ip"          { value = aws_instance.main.private_ip }
output "main_sg_id"               { value = aws_security_group.main.id }
output "gpu_sg_id"                { value = aws_security_group.gpu.id }
output "gpu_spot_request_id"      { value = aws_spot_instance_request.gpu.id }
output "app_secret_arn"           { value = aws_secretsmanager_secret.app.arn }
