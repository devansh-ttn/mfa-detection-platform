output "account_id" {
  description = "AWS account ID for the active credentials."
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region in use."
  value       = var.aws_region
}

output "name_prefix" {
  description = "Resource name prefix for this deployment."
  value       = local.name_prefix
}

# RDS

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (host:port)."
  value       = module.rds.endpoint
}

output "rds_port" {
  description = "RDS PostgreSQL port."
  value       = module.rds.port
}

output "rds_database_name" {
  description = "RDS database name."
  value       = module.rds.database_name
}

output "rds_security_group_id" {
  description = "Security group attached to RDS."
  value       = module.rds.security_group_id
}

# S3

output "evidence_bucket_name" {
  description = "S3 bucket for crawl evidence artifacts."
  value       = module.s3.evidence_bucket_name
}

output "evidence_bucket_arn" {
  description = "ARN of the evidence S3 bucket."
  value       = module.s3.evidence_bucket_arn
}

# SQS

output "batch_queue_url" {
  description = "Standard SQS queue URL for batch crawl/score jobs."
  value       = module.sqs.batch_queue_url
}

output "batch_queue_arn" {
  description = "ARN of the batch SQS queue."
  value       = module.sqs.batch_queue_arn
}

output "priority_queue_url" {
  description = "FIFO SQS queue URL for priority jobs."
  value       = module.sqs.priority_queue_url
}

output "priority_queue_arn" {
  description = "ARN of the priority FIFO SQS queue."
  value       = module.sqs.priority_queue_arn
}

# ECS

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN."
  value       = module.ecs.cluster_arn
}

output "ecs_task_definition_arns" {
  description = "Task definition ARNs for platform workers (stubs)."
  value       = module.ecs.task_definition_arns
}

# Cognito

output "cognito_user_pool_id" {
  description = "Cognito user pool ID for JWT validation."
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "Cognito SPA app client ID."
  value       = module.cognito.app_client_id
}

output "cognito_hosted_ui_domain" {
  description = "Cognito hosted UI domain (without https://)."
  value       = module.cognito.hosted_ui_domain
}

output "cognito_issuer" {
  description = "Cognito OIDC issuer URL."
  value       = module.cognito.issuer
}

# OpenSearch

output "opensearch_collection_endpoint" {
  description = "OpenSearch Serverless collection endpoint for RAG indexing."
  value       = module.opensearch.collection_endpoint
}

output "opensearch_index_name" {
  description = "Default RAG index name."
  value       = module.opensearch.index_name
}
