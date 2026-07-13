variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "tags" {
  type = map(string)
}

locals {
  name_prefix        = "${var.project_name}-${var.environment}"
  batch_queue_name   = "${local.name_prefix}-batch-queue"
  priority_queue_name = "${local.name_prefix}-priority-queue.fifo"
}

resource "aws_sqs_queue" "batch" {
  name                       = local.batch_queue_name
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600 # 14 days
  receive_wait_time_seconds  = 20      # long polling

  tags = merge(var.tags, {
    Name    = local.batch_queue_name
    purpose = "batch-jobs"
  })
}

resource "aws_sqs_queue" "priority" {
  name                        = local.priority_queue_name
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 300
  message_retention_seconds   = 1209600
  receive_wait_time_seconds   = 20

  tags = merge(var.tags, {
    Name    = local.priority_queue_name
    purpose = "priority-jobs"
  })
}

output "batch_queue_url" {
  value = aws_sqs_queue.batch.url
}

output "batch_queue_arn" {
  value = aws_sqs_queue.batch.arn
}

output "batch_queue_name" {
  value = aws_sqs_queue.batch.name
}

output "priority_queue_url" {
  value = aws_sqs_queue.priority.url
}

output "priority_queue_arn" {
  value = aws_sqs_queue.priority.arn
}

output "priority_queue_name" {
  value = aws_sqs_queue.priority.name
}
