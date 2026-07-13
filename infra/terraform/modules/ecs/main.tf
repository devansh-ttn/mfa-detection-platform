variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "task_cpu" {
  type = string
}

variable "task_memory" {
  type = string
}

variable "tags" {
  type = map(string)
}

locals {
  name_prefix  = "${var.project_name}-${var.environment}"
  cluster_name = "${local.name_prefix}-cluster"

  services = {
    backend_api = {
      family      = "${local.name_prefix}-backend-api"
      description = "FastAPI ingestion and scoring API"
      image       = "public.ecr.aws/docker/library/python:3.12-slim-bookworm"
      command     = ["echo", "backend-api task definition stub — replace with ECR image"]
    }
    crawler_worker = {
      family      = "${local.name_prefix}-crawler-worker"
      description = "Playwright crawl worker"
      image       = "public.ecr.aws/docker/library/python:3.12-slim-bookworm"
      command     = ["echo", "crawler-worker task definition stub — replace with ECR image"]
    }
    ml_worker = {
      family      = "${local.name_prefix}-ml-worker"
      description = "ML scoring worker"
      image       = "public.ecr.aws/docker/library/python:3.12-slim-bookworm"
      command     = ["echo", "ml-worker task definition stub — replace with ECR image"]
    }
  }
}

resource "aws_ecs_cluster" "main" {
  name = local.cluster_name

  setting {
    name  = "containerInsights"
    value = var.environment == "prod" ? "enabled" : "disabled"
  }

  tags = merge(var.tags, {
    Name = local.cluster_name
  })
}

resource "aws_cloudwatch_log_group" "ecs" {
  for_each = local.services

  name              = "/ecs/${each.value.family}"
  retention_in_days = var.environment == "prod" ? 30 : 7

  tags = merge(var.tags, {
    Name = "/ecs/${each.value.family}"
  })
}

resource "aws_ecs_task_definition" "services" {
  for_each = local.services

  family                   = each.value.family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = each.value.image
      essential = true
      command   = each.value.command

      environment = [
        { name = "ENV", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs[each.key].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = each.key
        }
      }
    },
  ])

  tags = merge(var.tags, {
    Name        = each.value.family
    description = each.value.description
  })
}

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-ecs-execution"
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-ecs-task"
  })
}

# TODO(MVP-1.2/1.3): Attach least-privilege policies for S3 evidence, SQS, and Secrets Manager.

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "task_definition_arns" {
  value = { for k, td in aws_ecs_task_definition.services : k => td.arn }
}

output "execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}
