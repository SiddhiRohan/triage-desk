variable "region" { default = "us-east-2" }

variable "ssh_public_key" {
  description = "contents of ~/.ssh/id_ed25519.pub"
}

# the brief's plan B shape. 2 vcpu / 8 gb, x86
variable "instance_type" { default = "m7i-flex.large" }

variable "root_gb" { default = 40 }
