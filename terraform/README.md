# Development EC2 Instance - Terraform Configuration

This Terraform configuration creates a single EC2 instance optimized for remote development work.

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **Terraform installed** (version >= 1.0)
3. **Existing VPC** in the us-east-2 region
4. **SSH Key Pair** created in AWS EC2

## Configuration

1. Copy the example configuration file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` and provide the required values:
   - `vpc_id`: Your existing VPC ID (format: vpc-xxxxxxxxx)
   - `key_name`: Your SSH key pair name (without .pem extension)

## Deployment

1. Initialize Terraform:
   ```bash
   terraform init
   ```

2. Plan the deployment:
   ```bash
   terraform plan
   ```

3. Apply the configuration:
   ```bash
   terraform apply
   ```

## What's Included

### EC2 Instance
- **Instance Type**: t3.medium (configurable)
- **AMI**: Latest Amazon Linux 2023
- **Storage**: 20GB GP3 encrypted root volume
- **Networking**: Public IP with Elastic IP for consistent access

### Security Group
The security group opens the following ports:
- **22 (SSH)**: For remote access
- **3000**: React/Node.js development server
- **5000**: Flask/FastAPI development server
- **8000**: General development server
- **8080**: Alternative development server

### Pre-installed Development Tools
- Python 3 with pip
- uv (modern Python package manager)
- Git
- Docker
- Node.js & npm
- AWS CLI v2
- Development tools (gcc, make, etc.)
- Utility tools (htop, tree, vim, nano, etc.)

## After Deployment

1. **Connect to your instance**:
   ```bash
   ssh -i ~/.ssh/your-key-pair.pem ec2-user@<ELASTIC_IP>
   ```
   (The exact command will be shown in the Terraform output)

2. **Run the setup script**:
   ```bash
   ~/setup-dev.sh
   ```

3. **Configure Git**:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

4. **Clone your project**:
   ```bash
   git clone <your-repo-url> ~/projects/banking-streamprocessing-demos
   ```

## Outputs

After deployment, Terraform will output:
- Instance ID
- Public IP address
- Private IP address
- SSH connection command
- Available development ports

## Cost Considerations

- **t3.medium**: ~$0.0416/hour (~$30/month if running 24/7)
- **GP3 Storage**: ~$0.08/month per GB
- **Elastic IP**: Free while attached to running instance

## Security Notes

- The security group allows SSH access from anywhere (0.0.0.0/0) by default
- For better security, modify `allowed_cidr_blocks` in `terraform.tfvars` to restrict access to your IP
- The instance uses encrypted storage
- All development ports are open to the internet for testing purposes

## Cleanup

To destroy the infrastructure:
```bash
terraform destroy
```

## Configuration Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `aws_region` | AWS region | us-east-2 | No |
| `vpc_id` | VPC ID | - | Yes |
| `key_name` | SSH key pair name | - | Yes |
| `instance_type` | EC2 instance type | t3.medium | No |
| `root_volume_size` | Root volume size (GB) | 20 | No |
| `project_name` | Project name for tagging | banking-streamprocessing-demos | No |
| `allowed_cidr_blocks` | CIDR blocks for SSH access | ["0.0.0.0/0"] | No | 