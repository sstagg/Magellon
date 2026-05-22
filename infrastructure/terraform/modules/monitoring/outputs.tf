output "sns_topic_arn"    { value = aws_sns_topic.alerts.arn }
output "dashboard_name"   { value = aws_cloudwatch_dashboard.magellon.dashboard_name }
