terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # TODO(MVP): Configure remote backend (S3 + DynamoDB lock) per environment.
  # backend "s3" {}
}
