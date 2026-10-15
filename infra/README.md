# infra

- `aws/`: what built the live VM. AWS Free plan, one m7i-flex.large in us-east-2, Ubuntu 24.04, default VPC, ports 22/80/443. See `aws/README.md`.
- `oracle/`: the first attempt. Oracle Always Free A1.Flex (2 OCPU / 12 GB) with its VCN. `terraform apply` returned "Out of host capacity" in every Ashburn availability domain for 15+ hours, so it was never used. Kept as evidence and because it is complete.
- `setup.sh`: everything after the VM exists: both runtimes, five agents, the app, Caddy. Run it once as the ubuntu user with four keys exported; the header of the file says which.

State files, tfvars and keys are git-ignored here (`.gitignore` in this folder).
