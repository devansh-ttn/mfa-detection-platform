variable "project_name" {
  description = "Short project prefix for resource names (e.g. mfa)."
  type        = string
  default     = "mfa"
}

variable "environment" {
  description = "Deploy environment: dev, staging, or prod."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}

# --- RDS ---

variable "rds_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.medium"
}

variable "rds_allocated_storage_gb" {
  description = "Initial allocated storage for RDS (GiB)."
  type        = number
  default     = 20
}

variable "rds_database_name" {
  description = "Default database name."
  type        = string
  default     = "mfa"
}

variable "rds_master_username" {
  description = "Master username for RDS. Password is managed in Secrets Manager (TODO MVP-1.2)."
  type        = string
  default     = "mfa_admin"
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ for RDS."
  type        = bool
  default     = false
}

variable "rds_deletion_protection" {
  description = "Enable deletion protection on RDS."
  type        = bool
  default     = false
}

variable "rds_skip_final_snapshot" {
  description = "Skip final snapshot on destroy (set false in prod)."
  type        = bool
  default     = true
}

# --- ECS ---

variable "ecs_task_cpu" {
  description = "Default Fargate CPU units for task definition stubs."
  type        = string
  default     = "512"
}

variable "ecs_task_memory" {
  description = "Default Fargate memory (MiB) for task definition stubs."
  type        = string
  default     = "1024"
}

# --- Cognito (MVP-4.6) ---

variable "cognito_callback_urls" {
  description = "OAuth callback URLs for the review console SPA."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "cognito_logout_urls" {
  description = "OAuth logout URLs for the review console SPA."
  type        = list(string)
  default     = ["http://localhost:5173"]
}
