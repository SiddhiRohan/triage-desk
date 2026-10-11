# infra/aws (plan B)

Oracle's Always Free A1 shape returned "Out of host capacity" in every Ashburn availability
domain for 15+ hours (see ../oracle). The brief's plan B is the AWS Free plan with
m7i-flex.large, so this is that: one Ubuntu 24.04 instance in the default VPC, ports 22/80/443.

    export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...   (or $env: in PowerShell)
    cp terraform.tfvars.example terraform.tfvars            # add your ssh public key
    terraform init && terraform apply

Tear down: `terraform destroy`. Stop the instance when not in use to save credits.
