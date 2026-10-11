terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
provider "aws" {
  region = var.region
}
