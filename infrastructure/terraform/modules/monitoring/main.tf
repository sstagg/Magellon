##############################################################################
# Monitoring Module
# CloudWatch: log groups, metric alarms (CPU, memory, disk), SNS alerts,
# and a single dashboard for both instances + ALB.
##############################################################################

# ── SNS topic for alarm notifications ─────────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "${var.name_prefix}-alerts"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch Log Groups (containers write here via awslogs driver) ──────────
resource "aws_cloudwatch_log_group" "main" {
  for_each          = toset(["backend", "web", "mysql", "rabbitmq", "dragonfly", "nats", "ctf-plugin"])
  name              = "/magellon/${var.name_prefix}/${each.key}"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "gpu" {
  name              = "/magellon/${var.name_prefix}/motioncor-plugin"
  retention_in_days = 30
  tags              = var.tags
}

# ── Alarms: Main instance CPU ─────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "main_cpu_high" {
  alarm_name          = "${var.name_prefix}-main-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "Main instance CPU > 85% for 3 consecutive minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions          = { InstanceId = var.main_instance_id }
  tags                = var.tags
}

# ── Alarms: GPU instance CPU ──────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "gpu_cpu_high" {
  alarm_name          = "${var.name_prefix}-gpu-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = 95
  alarm_description   = "GPU instance CPU > 95% – MotionCor may be stuck"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions          = { InstanceId = var.gpu_instance_id }
  tags                = var.tags
}

# ── Alarms: Main instance status checks ──────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "main_status_check" {
  alarm_name          = "${var.name_prefix}-main-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed_System"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Main instance status check failed – triggers auto-recovery"
  alarm_actions       = [
    aws_sns_topic.alerts.arn,
    "arn:aws:automate:${var.aws_region}:ec2:recover"
  ]
  dimensions = { InstanceId = var.main_instance_id }
  tags       = var.tags
}

# ── Alarms: ALB 5xx error rate ────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.name_prefix}-alb-5xx-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "ALB is returning 5xx errors – check backend"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { LoadBalancer = var.alb_arn_suffix }
  treat_missing_data  = "notBreaching"
  tags                = var.tags
}

# ── Alarms: ALB unhealthy host count ─────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  alarm_name          = "${var.name_prefix}-alb-unhealthy-hosts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 30
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "ALB target group has unhealthy hosts"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  tags = var.tags
}

# ── CloudWatch Dashboard ──────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "magellon" {
  dashboard_name = "${var.name_prefix}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Main Instance CPU"
          region  = var.aws_region
          metrics = [["AWS/EC2", "CPUUtilization", "InstanceId", var.main_instance_id]]
          period  = 60
          stat    = "Average"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "GPU Instance CPU"
          region  = var.aws_region
          metrics = [["AWS/EC2", "CPUUtilization", "InstanceId", var.gpu_instance_id]]
          period  = 60
          stat    = "Average"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "ALB Request Count"
          region  = var.aws_region
          metrics = [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "Sum"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "ALB 5xx Errors"
          region  = var.aws_region
          metrics = [["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "Sum"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title   = "ALB Target Response Time (p99)"
          region  = var.aws_region
          metrics = [["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix]]
          period  = 60
          stat    = "p99"
          view    = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title   = "EFS Burst Credits"
          region  = var.aws_region
          metrics = [["AWS/EFS", "BurstCreditBalance", "FileSystemId", var.efs_id]]
          period  = 300
          stat    = "Average"
          view    = "timeSeries"
        }
      }
    ]
  })
}
