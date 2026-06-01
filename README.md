# AI-Driven CloudFormation Validation Framework

Masters Research 2026 | Doshisha University | Network Information Systems Laboratory

## Overview
An automated three-gate framework that validates and self-heals AI-generated AWS CloudFormation templates using Claude AI, cfn-lint, cfn-nag, and LocalStack.

## Results (148 Experiments)
- Success Rate: 95.9%
- Avg Iterations: 0.93
- First Pass Rate: 30.4%
- Avg Time: 24.51 seconds

## Three-Gate Architecture
- **Gate 1**: cfn-lint + cfn-nag (static analysis + security scan)
- **Gate 1.5**: Best practice checks (ALB SG, passwords, Redis config)
- **Gate 2**: LocalStack runtime simulation (no AWS cost)

## Setup
```bash
pip install anthropic boto3 cfn-lint openpyxl
gem install cfn-nag --user-install
# Start LocalStack
docker run -d -p 4566:4566 localstack/localstack
```

## Usage
```bash
export ANTHROPIC_API_KEY="your-key"
export CFN_TEMPLATE_PATH="templates/your_template.yaml"
python3 pipeline.py
```

## Author
YERRAPOTHU VENKATA KESAVA SIVA SAI  
Supervisor: Professor KOITA Takahiro  
Doshisha University, 2026
