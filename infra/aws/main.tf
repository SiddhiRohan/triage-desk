# latest ubuntu 24.04 (x86, since m7i-flex is intel)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# new accounts come with a default vpc, use it
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_key_pair" "me" {
  key_name   = "triage-desk"
  public_key = var.ssh_public_key
}

resource "aws_security_group" "sg" {
  name        = "triage-desk"
  description = "ssh + web. dashboards stay on localhost behind an ssh tunnel"
  vpc_id      = data.aws_vpc.default.id

  dynamic "ingress" {
    for_each = [22, 80, 443]
    content {
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "vm" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.sg.id]
  key_name                    = aws_key_pair.me.key_name
  associate_public_ip_address = true

  root_block_device {
    volume_size = var.root_gb
    volume_type = "gp3"
  }

  tags = { Name = "triage-desk" }
}

output "public_ip" {
  value = aws_instance.vm.public_ip
}
