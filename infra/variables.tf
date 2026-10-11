# fill these in terraform.tfvars (git-ignored), not here

variable "tenancy_ocid" {}
variable "user_ocid" {}
variable "fingerprint" {}
variable "private_key_path" {}
variable "region" { default = "us-ashburn-1" }

variable "ssh_public_key" {
  description = "contents of ~/.ssh/id_ed25519.pub"
}

# if Oracle says "Out of host capacity", bump this to 1 or 2 and re-apply
variable "ad_index" {
  default = 0
}

# always-free limit as of mid 2026 is 2 ocpu / 12 gb. drop to 1/6 if capacity is tight
variable "ocpus" { default = 2 }
variable "memory_gb" { default = 12 }
