#!/bin/bash
set -e

# Update system
dnf update -y

# Install development tools
dnf groupinstall -y "Development Tools"
dnf install -y \
    git \
    htop \
    tree \
    vim \
    nano \
    curl \
    wget \
    unzip \
    python3 \
    python3-pip \
    python3-devel \
    sqlite \
    docker \
    jq

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Add ec2-user to docker group
usermod -a -G docker ec2-user

# Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Make uv available in PATH for ec2-user
echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/ec2-user/.bashrc

# Install Node.js (for potential frontend development)
curl -fsSL https://rpm.nodesource.com/setup_lts.x | bash -
dnf install -y nodejs

# Install AWS CLI v2
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install

# Create project directory
mkdir -p /home/ec2-user/projects
chown ec2-user:ec2-user /home/ec2-user/projects

# Set up git configuration placeholders
cat > /home/ec2-user/.gitconfig << EOF
[user]
    # Configure with: git config --global user.name "Your Name"
    # Configure with: git config --global user.email "your.email@example.com"
[init]
    defaultBranch = main
EOF

chown ec2-user:ec2-user /home/ec2-user/.gitconfig

# Create a helpful development script
cat > /home/ec2-user/setup-dev.sh << 'EOF'
#!/bin/bash
echo "Setting up development environment..."
echo "Project: ${project_name}"
echo ""
echo "Available tools:"
echo "- Python 3 with pip"
echo "- uv (modern Python package manager)"
echo "- Git"
echo "- Docker"
echo "- Node.js & npm"
echo "- AWS CLI v2"
echo ""
echo "Next steps:"
echo "1. Configure git: git config --global user.name 'Your Name'"
echo "2. Configure git: git config --global user.email 'your.email@example.com'"
echo "3. Clone your project: git clone <your-repo-url> ~/projects/${project_name}"
echo "4. Set up your development environment"
echo ""
echo "The projects directory is at: ~/projects"
echo "Docker is available and running"
EOF

chmod +x /home/ec2-user/setup-dev.sh
chown ec2-user:ec2-user /home/ec2-user/setup-dev.sh

# Display setup completion message
echo "Development environment setup complete!" >> /var/log/user-data.log
echo "Run ~/setup-dev.sh for next steps" >> /var/log/user-data.log 