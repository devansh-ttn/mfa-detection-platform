variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "instance_class" {
  type = string
}

variable "allocated_storage_gb" {
  type = number
}

variable "database_name" {
  type = string
}

variable "master_username" {
  type = string
}

variable "multi_az" {
  type = bool
}

variable "deletion_protection" {
  type = bool
}

variable "skip_final_snapshot" {
  type = bool
}

variable "tags" {
  type = map(string)
}

locals {
  name_prefix    = "${var.project_name}-${var.environment}"
  instance_id    = "${local.name_prefix}-postgres"
  subnet_grp_id  = "${local.name_prefix}-postgres-subnet"
  sg_id          = "${local.name_prefix}-postgres-sg"
}

resource "aws_db_subnet_group" "postgres" {
  name       = local.subnet_grp_id
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = local.subnet_grp_id
  })
}

resource "aws_security_group" "postgres" {
  name        = local.sg_id
  description = "PostgreSQL access for ${local.name_prefix}"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.selected.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = local.sg_id
  })
}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

resource "aws_db_parameter_group" "postgres16" {
  name        = "${local.name_prefix}-postgres16"
  family      = "postgres16"
  description = "PostgreSQL 16 parameters for ${local.name_prefix}"

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-postgres16"
  })
}

resource "aws_db_instance" "postgres" {
  identifier = local.instance_id

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.database_name
  username = var.master_username
  # TODO(MVP-1.2): Store password in Secrets Manager; use manage_master_user_password = true
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  parameter_group_name   = aws_db_parameter_group.postgres16.name
  publicly_accessible    = false

  multi_az               = var.multi_az
  deletion_protection    = var.deletion_protection
  skip_final_snapshot    = var.skip_final_snapshot
  backup_retention_period = var.environment == "prod" ? 7 : 1

  tags = merge(var.tags, {
    Name = local.instance_id
  })
}

output "endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "port" {
  value = aws_db_instance.postgres.port
}

output "database_name" {
  value = aws_db_instance.postgres.db_name
}

output "security_group_id" {
  value = aws_security_group.postgres.id
}

output "instance_arn" {
  value = aws_db_instance.postgres.arn
}
