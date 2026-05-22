output "efs_id"                    { value = aws_efs_file_system.this.id }
output "efs_dns"                   { value = aws_efs_file_system.this.dns_name }
output "efs_sg_id"                 { value = aws_security_group.efs.id }
output "ap_magellon_id"           { value = aws_efs_access_point.magellon.id }
output "ap_gpfs_id"               { value = aws_efs_access_point.gpfs.id }
output "ap_jobs_id"               { value = aws_efs_access_point.jobs.id }
