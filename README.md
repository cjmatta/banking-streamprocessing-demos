# banking Stream Processing Demos

This repository contains stream processing demonstrations and use cases for monitoring and alerting systems.

## Project Structure

```
banking-streamprocessing-demos/
├── terraform/                          # Infrastructure as Code
│   ├── main.tf                        # EC2 instance configuration
│   ├── variables.tf                   # Configuration variables
│   ├── outputs.tf                     # Terraform outputs
│   ├── user_data.sh                   # Instance bootstrap script
│   ├── terraform.tfvars.example       # Example configuration
│   └── README.md                      # Terraform documentation
├── undelivered-message-alert/         # Use Case 1: Message delivery monitoring
│   ├── main.py                        # Main application
│   ├── phone_message_producer.py      # Message producer logic
│   ├── message_tracking.db            # SQLite database
│   ├── message-tracking.json          # Configuration
│   ├── pyproject.toml                 # Python dependencies
│   └── README.md                      # Use case documentation
└── README.md                          # This file
```

## Use Cases

### Use Case 1: Message Delivery Status Monitoring
Located in `undelivered-message-alert/`

**Objective:** Track the delivery status of messages (e.g., SMS OTPs) sent via third-party providers to ensure they are delivered within a specified time frame.

**Problem:** Previous issues occurred where messages to specific carriers were delayed without any proactive detection mechanism.

**Solution:** A stateful stream processor that tracks message IDs and their delivery status, alerting when messages remain undelivered after a configurable timeout.

## Development Infrastructure

### Remote Development on AWS EC2

The `terraform/` directory contains Infrastructure as Code to provision a development EC2 instance optimized for remote development work.

#### Quick Start

1. **Prerequisites:**
   - AWS CLI configured
   - Terraform installed
   - Existing VPC in us-east-2
   - SSH key pair in AWS

2. **Deploy the infrastructure:**
   ```bash
   cd terraform/
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your VPC ID and SSH key name
   terraform init
   terraform apply
   ```

3. **Connect to your instance:**
   ```bash
   ssh -i ~/.ssh/your-key.pem ec2-user@<ELASTIC_IP>
   ```

4. **Set up development environment:**
   ```bash
   ~/setup-dev.sh
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

#### What's Included

- **EC2 Instance:** t3.medium with Amazon Linux 2023
- **Development Tools:** Python 3, uv, Git, Docker, Node.js, AWS CLI
- **Security:** Encrypted storage, configurable security groups
- **Networking:** Elastic IP for consistent access
- **Ports:** SSH (22), and development ports (3000, 5000, 8000, 8080)

See [terraform/README.md](terraform/README.md) for detailed documentation.

## Local Development

### Prerequisites

- Python 3.8+
- uv (recommended) or pip

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd banking-streamprocessing-demos
   ```

2. **Navigate to a use case:**
   ```bash
   cd undelivered-message-alert/
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   # or
   pip install -r pyproject.toml
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

## Contributing

1. Create a feature branch
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## Cost Considerations

If using the AWS infrastructure:
- **t3.medium:** ~$30/month (if running 24/7)
- **Storage:** ~$1.60/month for 20GB
- **Elastic IP:** Free while attached

Remember to `terraform destroy` when not actively developing to avoid costs.

## Security Notes

- The default security group allows SSH access from anywhere
- For production use, restrict access to your IP address
- All development ports are open for testing purposes
- Instance storage is encrypted 