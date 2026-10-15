# infra

One always-free Oracle A1 VM (2 ocpu / 12 gb, Ubuntu 24.04 aarch64) plus the VCN around it.

    cp terraform.tfvars.example terraform.tfvars   # then fill it in
    terraform init
    terraform plan
    terraform apply

Out of host capacity? `terraform apply -var ad_index=1` (then 2). Still stuck: `-var ocpus=1 -var memory_gb=6`.

Tear down: `terraform destroy`.
