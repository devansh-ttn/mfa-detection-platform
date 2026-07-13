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
  name_prefix    = "${var.project_name}-${var.environment}"
  collection_name = "${local.name_prefix}-rag"
}

# OpenSearch Serverless collection for RAG hybrid search (MVP-3.1).
# Data access policies must be attached after ECS task roles are known.

resource "aws_opensearchserverless_collection" "rag" {
  name = local.collection_name
  type = "SEARCH"
}

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${local.name_prefix}-rag-encryption"
  type = "encryption"

  policy = jsonencode({
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.collection_name}"]
      }
    ]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${local.name_prefix}-rag-network"
  type = "network"

  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${local.collection_name}"]
        }
      ]
      AllowFromPublic = var.environment != "prod"
    }
  ])
}

output "collection_id" {
  value = aws_opensearchserverless_collection.rag.id
}

output "collection_endpoint" {
  value = aws_opensearchserverless_collection.rag.collection_endpoint
}

output "collection_arn" {
  value = aws_opensearchserverless_collection.rag.arn
}

output "index_name" {
  value = "mfa-rag-v1"
}
