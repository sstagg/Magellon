##############################################################################
# EFS Module
# Shared POSIX filesystem mounted by both the main CPU instance and the GPU
# instance.  Replaces host bind-mounts (/magellon, /gpfs, /jobs) so both
# instances see the same data without any manual rsync.
##############################################################################

resource "aws_efs_file_system" "this" {
  creation_token   = "${var.name_prefix}-shared"
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"
  encrypted        = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  lifecycle_policy {
    transition_to_primary_storage_class = "AFTER_1_ACCESS"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-efs" })
}

# ── Security group for EFS mount targets ──────────────────────────────────────
resource "aws_security_group" "efs" {
  name        = "${var.name_prefix}-efs-sg"
  description = "Allow NFS from instances in the VPC"
  vpc_id      = var.vpc_id

  ingress {
    description = "NFS from private subnets"
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    cidr_blocks = var.private_subnet_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-efs-sg" })
}

# ── Mount targets (one per private subnet / AZ) ───────────────────────────────
resource "aws_efs_mount_target" "this" {
  count           = length(var.private_subnet_ids)
  file_system_id  = aws_efs_file_system.this.id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}

# ── Access points ─────────────────────────────────────────────────────────────
resource "aws_efs_access_point" "magellon" {
  file_system_id = aws_efs_file_system.this.id
  posix_user {
    uid = 1000
    gid = 1000
  }
  root_directory {
    path = "/magellon"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-efs-ap-magellon" })
}

resource "aws_efs_access_point" "gpfs" {
  file_system_id = aws_efs_file_system.this.id
  posix_user {
    uid = 1000
    gid = 1000
  }
  root_directory {
    path = "/gpfs"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-efs-ap-gpfs" })
}

resource "aws_efs_access_point" "jobs" {
  file_system_id = aws_efs_file_system.this.id
  posix_user {
    uid = 1000
    gid = 1000
  }
  root_directory {
    path = "/jobs"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-efs-ap-jobs" })
}

resource "aws_efs_backup_policy" "this" {
  file_system_id = aws_efs_file_system.this.id
  backup_policy {
    status = "ENABLED"
  }
}
