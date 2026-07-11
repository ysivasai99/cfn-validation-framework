# AI-Driven CloudFormation Validation Framework
Masters Research 2026 | Doshisha University | Network Information Systems Laboratory

## Overview
An automated three-gate framework that validates and self-heals AI-generated AWS CloudFormation templates using Claude AI, cfn-lint, cfn-nag, and LocalStack.

## Results (116 Templates)
| Metric | Value |
|--------|-------|
| Success Rate | 89.7% (104/116) |
| Escalated | 10.3% (12/116) |
| Failed | 0% |
| First Pass Rate | 13.8% (16/116) |
| Avg Iterations | 1.40 ± 0.95 |
| Median Iterations | 1.0 |
| Avg Time | 25.86 seconds |
| Fastest Fix | 6.94 seconds |
| Max Errors Fixed | 10 |
| AWS Service Categories | 16 |
| Wilson 95% CI | [82.8%, 94.0%] |
| Productivity ROI | ~1,137× |

## Three-Gate Architecture
- **Gate 1**: cfn-lint + cfn-nag (static analysis + security scan) — 2–3 sec, free
- **Gate 1.5**: 6 custom best practice checks (ALB SG, EC2 SG, passwords, Redis config) — <1 sec, free
- **Gate 2**: LocalStack runtime simulation — 10–60 sec, free (no AWS cost)
- **Self-Healing Loop**: Claude Sonnet 4.5 auto-correction — max 8 iterations

## Gate Progression (Empirically Measured)
| Validation Stage | Success Rate |
|-----------------|--------------|
| Raw Claude (no validation) | 13.8% |
| Gate 1 only (cfn-lint + cfn-nag) | 51.7% |
| Gate 1 + 1.5 | 58.6% |
| Full Framework (all 3 gates) | 89.7% |

## Error Taxonomy (187 total instances)
| Error Type | Frequency |
|------------|-----------|
| syntax_error | 34.2% |
| runtime_error | 25.1% |
| wrong_value | 17.6% |
| best_practice | 12.8% |

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

## Cost Analysis
| Factor | Without Framework | With Framework |
|--------|------------------|----------------|
| AWS infra cost | ~$2.10 | $0.00 |
| Claude API cost | $0.00 | $2.55 |
| Engineer time | ~58 hours | ~0 hours |
| Total cost | ~$2,902.10 | $2.55 |
| **ROI** | | **~1,137×** |

## Paper
- **Title**: Evaluation of an Automated Validation Framework for AI-Generated AWS CloudFormation Templates
- **Conference**: ICAISE 2026 (Paper ID: CC5025)
- **Authors**: Yerrapothu V.K. Siva Sai, Akihito Kohiga, Takahiro Koita

## Author
YERRAPOTHU VENKATA KESAVA SIVA SAI
Supervisor: Professor KOITA Takahiro & Professor KOHIGA Akihito
Doshisha University, Network Information Systems Laboratory, 2026
