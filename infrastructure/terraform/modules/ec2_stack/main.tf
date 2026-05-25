##############################################################################
# EC2 Stack Module
# Creates security groups + both EC2 instances (main CPU + GPU spot).
#
# Security model:
#   alb_sg       → main_sg  (port 8080 only – frontend)
#   gpu_sg       → main_sg  (5672 RabbitMQ, 4222 NATS, 6379 Dragonfly)
#   main_sg      → anywhere (outbound for Docker pulls, EFS, ECR)
#   gpu_sg       → anywhere (outbound for Docker pulls, EFS, ECR)
#   Both instances: NO public IP. Access via SSM Session Manager only.
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

  # Frontend from ALB only
  ingress {
    description     = "Frontend from ALB"
    from_port       = var.frontend_port
    to_port         = var.frontend_port
    protocol        = "tcp"
    security_groups = [var.alb_sg_id]
  }

  # RabbitMQ AMQP from GPU worker only
  ingress {
    description     = "RabbitMQ from GPU"
    from_port       = 5672
    to_port         = 5672
    protocol        = "tcp"
    security_groups = [aws_security_group.gpu.id]
  }

  # NATS from GPU worker only
  ingress {
    description     = "NATS from GPU"
    from_port       = 4222
    to_port         = 4222
    protocol        = "tcp"
    security_groups = [aws_security_group.gpu.id]
  }

  # Dragonfly from GPU worker only
  ingress {
    description     = "Dragonfly/Redis from GPU"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.gpu.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-main-sg" })
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
    MYSQL_ROOT_PASSWORD      = var.mysql_root_password
    MYSQL_DATABASE           = var.mysql_database
    MYSQL_USER               = var.mysql_user
    MYSQL_PASSWORD           = var.mysql_password
    RABBITMQ_DEFAULT_USER    = var.rabbitmq_user
    RABBITMQ_DEFAULT_PASS    = var.rabbitmq_password
    DRAGONFLY_PASSWORD       = var.dragonfly_password
    GRAFANA_USER_NAME        = var.grafana_user
    GRAFANA_USER_PASS        = var.grafana_password
  })
}

# ── Main CPU Instance ─────────────────────────────────────────────────────────
resource "aws_instance" "main" {
  ami                         = data.aws_ami.ubuntu_22.id
  instance_type               = var.main_instance_type
  subnet_id                   = var.private_subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.main.id]
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = false  # private subnet, no public IP

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.main_volume_size
    iops                  = 3000
    throughput            = 125
    encrypted             = true
    delete_on_termination = false  # preserve data on accidental termination
  }

  user_data = base64encode(templatefile(
    "${path.module}/../../scripts/user_data_main.sh",
    {
      efs_id          = var.efs_id
      aws_region      = var.aws_region
      secret_arn      = aws_secretsmanager_secret.app.arn
      mysql_database  = var.mysql_database
      mysql_user      = var.mysql_user
      rabbitmq_user   = var.rabbitmq_user
      grafana_user    = var.grafana_user
    }
  ))

  # Enable detailed monitoring for CloudWatch
  monitoring = true

  # Auto-recovery on hardware failure
  maintenance_options { auto_recovery = "default" }

  tags       = merge(var.tags, { Name = "${var.name_prefix}-main" })
  volume_tags = merge(var.tags, { Name = "${var.name_prefix}-main-root" })

  depends_on = [aws_secretsmanager_secret_version.app]
}

# ── GPU Spot Instance ─────────────────────────────────────────────────────────
resource "aws_spot_instance_request" "gpu" {
  ami                            = data.aws_ami.dlami.id
  instance_type                  = var.gpu_instance_type
  spot_price                     = var.gpu_spot_max_price
  spot_type                      = "persistent"
  instance_interruption_behavior = "stop"
  wait_for_fulfillment           = true

  subnet_id                   = var.private_subnet_ids[1]
  vpc_security_group_ids      = [aws_security_group.gpu.id]
  associate_public_ip_address = false

  iam_instance_profile = var.instance_profile_name
  key_name             = var.key_pair_name
  monitoring           = true

  user_data = base64encode(templatefile(
    "${path.module}/../../scripts/user_data_gpu.sh",
    {
      efs_id           = var.efs_id
      aws_region       = var.aws_region
      secret_arn       = aws_secretsmanager_secret.app.arn
      main_private_ip  = aws_instance.main.private_ip
      rabbitmq_user    = var.rabbitmq_user
      cuda_image       = var.cuda_image
      motioncor_binary = var.motioncor_binary
    }
  ))

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.gpu_volume_size
    encrypted             = true
    delete_on_termination = false
  }

  tags        = merge(var.tags, { Name = "${var.name_prefix}-gpu-spot-request" })
  volume_tags = merge(var.tags, { Name = "${var.name_prefix}-gpu-root" })

  depends_on = [aws_instance.main]
}
