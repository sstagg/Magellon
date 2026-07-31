##############################################################################
# EC2 Stack Module
# Creates security groups, Route 53 private DNS, Secrets Manager, and both
# EC2 instances (main CPU + GPU spot).
#
# Security model:
#   alb_sg       → main_sg  (port 8080 only – frontend)
#   gpu_sg       → main_sg  (5672 RabbitMQ, 4222 NATS, 6379 Dragonfly)
#   main_sg      → anywhere (outbound for Docker pulls, EFS, ECR)
#   gpu_sg       → anywhere (outbound for Docker pulls, EFS, ECR)
#   Both instances: NO public IP. Access via SSM Session Manager only.
#
# DNS model (scalable):
#   GPU instances resolve rabbitmq/nats/dragonfly via Route 53 private zone
#   (magellon.internal). When the main EC2 is replaced, only the DNS A record
#   changes — GPU instances reconnect on next lookup with no config change.
##############################################################################

# ── Latest Ubuntu 22.04 LTS (main instance) ───────────────────────────────────
data "aws_ami" "ubuntu_22" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# ── AWS Deep Learning AMI (GPU instance – NVIDIA drivers pre-installed) ────────
data "aws_ami" "dlami" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning OSS Nvidia Driver AMI GPU PyTorch*(Ubuntu 22.04)*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

# ── Security Group: Main CPU instance ────────────────────────────────────────
resource "aws_security_group" "main" {
  name        = "${var.name_prefix}-main-sg"
  description = "Main stack: receives traffic from ALB and GPU worker"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-main-sg" })

  # Ingress rules are managed exclusively via aws_security_group_rule resources
  # below to avoid inline/separate-rule conflicts on every terraform apply.
  lifecycle {
    ignore_changes = [ingress]
  }
}

# ── Security Group: GPU spot instance ────────────────────────────────────────
resource "aws_security_group" "gpu" {
  name        = "${var.name_prefix}-gpu-sg"
  description = "GPU worker: MotionCor plugin only, outbound to main broker ports"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-gpu-sg" })
}

# ── Cross-SG rules (separated to avoid circular dependency) ──────────────────
resource "aws_security_group_rule" "main_from_gpu_rabbitmq" {
  type                     = "ingress"
  description              = "RabbitMQ from GPU"
  from_port                = 5672
  to_port                  = 5672
  protocol                 = "tcp"
  security_group_id        = aws_security_group.main.id
  source_security_group_id = aws_security_group.gpu.id
}

resource "aws_security_group_rule" "main_from_gpu_nats" {
  type                     = "ingress"
  description              = "NATS from GPU"
  from_port                = 4222
  to_port                  = 4222
  protocol                 = "tcp"
  security_group_id        = aws_security_group.main.id
  source_security_group_id = aws_security_group.gpu.id
}

resource "aws_security_group_rule" "main_from_gpu_dragonfly" {
  type                     = "ingress"
  description              = "Dragonfly/Redis from GPU"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  security_group_id        = aws_security_group.main.id
  source_security_group_id = aws_security_group.gpu.id
}

resource "aws_security_group_rule" "gpu_from_main_plugin" {
  type                     = "ingress"
  description              = "Plugin HTTP from main EC2"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.gpu.id
  source_security_group_id = aws_security_group.main.id
}

# ── Route 53 private hosted zone ─────────────────────────────────────────────
# GPU instances resolve broker services by DNS name, never by IP.
# When the main EC2 is replaced (new deployment, new private IP), only the
# A records below change. All GPU instances reconnect automatically.
resource "aws_route53_zone" "internal" {
  name    = "magellon.internal"
  comment = "Internal service discovery — GPU instances resolve brokers here"

  vpc {
    vpc_id = var.vpc_id
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-internal-zone" })
}

resource "aws_route53_record" "rabbitmq" {
  zone_id = aws_route53_zone.internal.zone_id
  name    = "rabbitmq.magellon.internal"
  type    = "A"
  ttl     = 60
  records = [aws_instance.main.private_ip]
}

resource "aws_route53_record" "nats" {
  zone_id = aws_route53_zone.internal.zone_id
  name    = "nats.magellon.internal"
  type    = "A"
  ttl     = 60
  records = [aws_instance.main.private_ip]
}

resource "aws_route53_record" "dragonfly" {
  zone_id = aws_route53_zone.internal.zone_id
  name    = "dragonfly.magellon.internal"
  type    = "A"
  ttl     = 60
  records = [aws_instance.main.private_ip]
}

# ── Secrets Manager: store application secrets ────────────────────────────────
resource "aws_secretsmanager_secret" "app" {
  name                    = "/magellon/${var.name_prefix}/app-secrets"
  description             = "Magellon application secrets"
  recovery_window_in_days = 7
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    MYSQL_ROOT_PASSWORD   = var.mysql_root_password
    MYSQL_DATABASE        = var.mysql_database
    MYSQL_USER            = var.mysql_user
    MYSQL_PASSWORD        = var.mysql_password
    RABBITMQ_DEFAULT_USER = var.rabbitmq_user
    RABBITMQ_DEFAULT_PASS = var.rabbitmq_password
    DRAGONFLY_PASSWORD    = var.dragonfly_password
    GRAFANA_USER_NAME     = var.grafana_user
    GRAFANA_USER_PASS     = var.grafana_password
  })
}

# ── Main CPU Instance ─────────────────────────────────────────────────────────
resource "aws_instance" "main" {
  ami                         = data.aws_ami.ubuntu_22.id
  instance_type               = var.main_instance_type
  subnet_id                   = var.private_subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.main.id]
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = false
  disable_api_termination     = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.main_volume_size
    iops                  = 3000
    throughput            = 125
    encrypted             = true
    delete_on_termination = false
  }

  user_data = base64encode(templatefile(
    "${path.module}/../../scripts/user_data_main.sh",
    {
      efs_id         = var.efs_id
      ap_magellon_id = var.ap_magellon_id
      ap_gpfs_id     = var.ap_gpfs_id
      ap_jobs_id     = var.ap_jobs_id
      aws_region     = var.aws_region
      secret_arn     = aws_secretsmanager_secret.app.arn
      mysql_database = var.mysql_database
      mysql_user     = var.mysql_user
      rabbitmq_user  = var.rabbitmq_user
      grafana_user   = var.grafana_user
      repo_branch    = var.repo_branch
    }
  ))

  monitoring = true
  maintenance_options { auto_recovery = "default" }

  tags        = merge(var.tags, { Name = "${var.name_prefix}-main" })
  volume_tags = merge(var.tags, { Name = "${var.name_prefix}-main-root" })

  depends_on = [aws_secretsmanager_secret_version.app]

  # Never auto-replace the running instance due to AMI patches or user_data
  # drift. OS updates are applied in-band; user_data only runs at launch.
  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# ── GPU auto-restart on hardware failure ──────────────────────────────────────
# G-family GPU instances don't support EC2 auto-recovery (C/M/R/T/X only).
# Strategy: CloudWatch alarm on StatusCheckFailed_System stops the instance
# (migrating off the bad host), then an EventBridge rule + Lambda restarts it
# automatically on healthy hardware.  This replicates the manual stop→start fix.

data "aws_caller_identity" "current" {}

# Lambda code packaged via archive_file — no external tooling required
data "archive_file" "gpu_restart" {
  type        = "zip"
  output_path = "${path.module}/gpu_restart_lambda.zip"
  source {
    filename = "index.py"
    content  = <<-PYTHON
      import boto3, os
      def handler(event, context):
          instance_id = os.environ['INSTANCE_ID']
          ec2 = boto3.client('ec2')
          ec2.start_instances(InstanceIds=[instance_id])
          print(f"Restarted GPU instance {instance_id} after hardware failure")
    PYTHON
  }
}

resource "aws_iam_role" "gpu_restart" {
  name               = "${var.name_prefix}-gpu-restart-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "gpu_restart" {
  name = "${var.name_prefix}-gpu-restart-policy"
  role = aws_iam_role.gpu_restart.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ec2:StartInstances", "ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "gpu_restart" {
  function_name    = "${var.name_prefix}-gpu-restart"
  role             = aws_iam_role.gpu_restart.arn
  runtime          = "python3.12"
  handler          = "index.handler"
  timeout          = 30
  filename         = data.archive_file.gpu_restart.output_path
  source_code_hash = data.archive_file.gpu_restart.output_base64sha256
  environment {
    variables = { INSTANCE_ID = aws_instance.gpu.id }
  }
  tags = var.tags
}

resource "aws_lambda_permission" "gpu_restart_eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gpu_restart.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.gpu_stopped.arn
}

# Fires when the GPU instance reaches "stopped" state (triggered by the alarm below)
resource "aws_cloudwatch_event_rule" "gpu_stopped" {
  name        = "${var.name_prefix}-gpu-stopped"
  description = "GPU instance stopped — Lambda restarts it on healthy hardware"
  event_pattern = jsonencode({
    source        = ["aws.ec2"]
    "detail-type" = ["EC2 Instance State-change Notification"]
    detail = {
      state       = ["stopped"]
      "instance-id" = [aws_instance.gpu.id]
    }
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "gpu_restart" {
  rule = aws_cloudwatch_event_rule.gpu_stopped.name
  arn  = aws_lambda_function.gpu_restart.arn
}

# Alarm: 2 consecutive minutes of system check failure → stop the instance
resource "aws_cloudwatch_metric_alarm" "gpu_hardware_failure" {
  alarm_name          = "${var.name_prefix}-gpu-hardware-failure"
  alarm_description   = "GPU system status check failed (hardware retirement/degradation). Stops instance; EventBridge+Lambda then restarts it on healthy hardware."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_System"
  dimensions          = { InstanceId = aws_instance.gpu.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = ["arn:aws:automate:${var.aws_region}:ec2:stop"]
  tags                = var.tags
}

# ── GPU Instance (on-demand) ──────────────────────────────────────────────────
# GPU instances use DNS names (rabbitmq.magellon.internal etc.) — never
# hardcoded IPs. On-demand avoids spot interruptions mid-job (MotionCor
# processes can run for hours). Switch back to aws_spot_instance_request
# when a reliable AZ with capacity is identified.
resource "aws_instance" "gpu" {
  ami                         = data.aws_ami.dlami.id
  instance_type               = var.gpu_instance_type
  subnet_id                   = var.private_subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.gpu.id]
  associate_public_ip_address = false
  disable_api_termination     = true

  iam_instance_profile = var.instance_profile_name
  key_name             = var.key_pair_name != "" ? var.key_pair_name : null
  monitoring           = true

  user_data = base64encode(templatefile(
    "${path.module}/../../scripts/user_data_gpu.sh",
    {
      efs_id           = var.efs_id
      ap_magellon_id   = var.ap_magellon_id
      ap_gpfs_id       = var.ap_gpfs_id
      ap_jobs_id       = var.ap_jobs_id
      aws_region       = var.aws_region
      secret_arn       = aws_secretsmanager_secret.app.arn
      rabbitmq_user    = var.rabbitmq_user
      cuda_image       = var.cuda_image
      motioncor_binary = var.motioncor_binary
      repo_branch      = var.repo_branch
    }
  ))

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.gpu_volume_size
    encrypted             = true
    delete_on_termination = false
  }

  tags        = merge(var.tags, { Name = "${var.name_prefix}-gpu" })
  volume_tags = merge(var.tags, { Name = "${var.name_prefix}-gpu-root" })

  depends_on = [
    aws_route53_record.rabbitmq,
    aws_route53_record.nats,
    aws_route53_record.dragonfly,
  ]

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}
