# Installation Guide

## Prerequisites
- Ubuntu 22.04 (WSL2 on Windows 11)
- Python 3.10+
- Docker Desktop
- Ruby 3.0+

## Step 1: Python Dependencies
```bash
pip install anthropic boto3 cfn-lint openpyxl
```

## Step 2: cfn-nag (Security Scanner)
```bash
gem install cfn-nag --user-install
echo 'export PATH="$HOME/.local/share/gem/ruby/3.0.0/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
cfn_nag_scan --version  # Should show 0.8.10
```

## Step 3: LocalStack (AWS Simulator)
```bash
docker pull localstack/localstack
docker run -d -p 4566:4566 localstack/localstack
```

## Step 4: AWS CLI Configure (for LocalStack)
```bash
aws configure
# AWS Access Key ID: test
# AWS Secret Access Key: test
# Default region: us-east-1
```

## Step 5: Anthropic API Key
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Step 6: Run Single Template
```bash
export CFN_TEMPLATE_PATH="templates/vpc_ec2_01.yaml"
python3 pipeline.py
```

## Step 7: Run All 116 Experiments
```bash
python3 run_all.py
```

## Results
Results saved to:
- `research_results/cfn_research_results.xlsx`
- `research_results/cfn_research_results.csv`
