import subprocess
import re
import os
import sys
import time
from pathlib import Path
from google import genai

client_gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

sys.path.insert(0, str(Path(__file__).parent))
from results_tracker import add_result, make_record

ORIGINAL_TEMPLATE_PATH = os.environ.get("CFN_TEMPLATE_PATH", "/home/ysivasai99/cfn-pipeline/broken_template.yaml")
original_name          = Path(ORIGINAL_TEMPLATE_PATH).stem
FINAL_FIXED_PATH       = f"/home/ysivasai99/cfn-pipeline/fixed_templates/final_{original_name}_gemini_fixed.yaml"
TEMP_PATH              = "/tmp/cfn_current_template.yaml"
MAX_ITERATIONS         = 5
MODEL_NAME             = "Gemini"

ERROR_PATTERNS = [
    {"pattern": r"'(.+)' is not a '(.+)' with pattern", "type": "wrong_value",  "hint": "Value doesn't match required pattern."},
    {"pattern": r"does not match '(.+)'",                "type": "wrong_value",  "hint": "Value format incorrect."},
    {"pattern": r"Avoid hardcoding availability zones",   "type": "wrong_value",  "hint": "Use !Select [0, !GetAZs '']"},
    {"pattern": r"Invalid id '(.+)'",                    "type": "missing_ref",  "hint": "Referenced ID not valid."},
    {"pattern": r"'(.+)' is not valid",                  "type": "wrong_value",  "hint": "Value not accepted by AWS."},
    {"pattern": r"DBInstanceClass",                      "type": "wrong_value",  "hint": "Use a valid DBInstanceClass like db.t3.micro"},
    {"pattern": r"InstanceType.*is not",                 "type": "wrong_value",  "hint": "Use a valid InstanceType like t2.micro"},
    {"pattern": r"Engine.*is not",                       "type": "wrong_value",  "hint": "Use a valid Engine like mysql or postgres"},
]

def run_cfn_lint(template_content):
    with open(TEMP_PATH, "w") as f: f.write(template_content)
    result = subprocess.run(["cfn-lint", TEMP_PATH], capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def parse_errors(lint_output):
    errors = []
    for line in lint_output.splitlines():
        if not line.strip() or line.startswith("/"): continue
        severity = "ERROR" if line.startswith("E") else "WARNING"
        error_type = "syntax_error"; hint = "Review this line."
        for ep in ERROR_PATTERNS:
            if re.search(ep["pattern"], line):
                error_type = ep["type"]; hint = ep["hint"]; break
        errors.append({"severity": severity, "message": line.strip(), "type": error_type, "hint": hint})
    return errors

def build_reprompt(template_yaml, errors, iteration):
    errors_text = "\n".join([f"- [{e['severity']}] {e['message'][:200]}\n  Hint: {e['hint']}" for e in errors])
    return f"""You are a CloudFormation expert. Fix these errors.
ITERATION: {iteration} of {MAX_ITERATIONS}
ERRORS:
{errors_text}
TEMPLATE:
{template_yaml}
INSTRUCTIONS:
1. Fix ONLY the erroring properties
2. For invalid AZ: use !Select [0, !GetAZs '']
3. For invalid S3 name: lowercase letters, numbers, hyphens only
4. For invalid AMI: use ami-0c02fb55956c7d316
5. For invalid DBInstanceClass: use db.t3.micro
6. For invalid InstanceType: use t2.micro
7. For invalid Engine: use mysql
8. Return ONLY corrected YAML, no explanation, no markdown fences
"""

def call_ai(prompt):
    print("   Calling Gemini API...")
    response = client_gemini.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text.strip()

def clean_template(content):
    if "```yaml" in content: content = content.split("```yaml")[1].split("```")[0].strip()
    elif "```" in content: content = content.split("```")[1].split("```")[0].strip()
    return content

def detect_template_type(template):
    if "RDS" in template: return "RDS + VPC"
    if "Lambda" in template and "DynamoDB" in template: return "Lambda + DynamoDB"
    if "Lambda" in template and "EventSourceMapping" in template: return "Lambda + SQS"
    if "Lambda" in template: return "S3 + Lambda"
    if "DynamoDB" in template: return "DynamoDB"
    if "KinesisFirehose" in template: return "Kinesis Firehose"
    if "Kinesis" in template: return "Kinesis"
    if "ElastiCache" in template: return "ElastiCache + VPC"
    if "StepFunctions" in template: return "Step Functions"
    if "CloudFront" in template: return "S3 + CloudFront"
    if "IAM" in template and "CloudWatch" in template: return "CloudWatch + IAM"
    if "IAM" in template: return "IAM"
    if "S3" in template and "EC2" in template: return "VPC + EC2 + S3"
    if "EC2" in template and "LoadBalancer" in template: return "EC2 + ALB"
    if "EC2" in template: return "VPC + EC2"
    if "S3" in template: return "S3 Bucket"
    if "SQS" in template or "SNS" in template: return "SQS + SNS"
    if "ECS" in template: return "ECS + ECR"
    if "CloudWatch" in template: return "CloudWatch"
    return "General CFN"

def save_success(current_template, total_fixes, total_errors, all_error_types, start_time, template_type, exp_id, note=""):
    elapsed = time.time() - start_time
    with open(FINAL_FIXED_PATH, "w") as f: f.write(current_template)
    print(f"\n SUCCESS! Valid after {total_fixes} fix(es) | Time: {elapsed:.1f}s")
    print(f" Saved → {Path(FINAL_FIXED_PATH).name}")
    record = make_record(exp_id, template_type, MODEL_NAME,
                         first_pass=(total_fixes == 0), iterations=total_fixes,
                         errors_found=total_errors, error_types=list(set(all_error_types)),
                         final_status="SUCCESS", time_seconds=elapsed,
                         aws_cost_saved=0.05, notes=note or f"{total_fixes} iterations")
    add_result(record)
    print("\nFINAL TEMPLATE:"); print("-" * 40)
    print(current_template)

def run_pipeline():
    print("=" * 60)
    print("  AI-CFN SELF-HEALING PIPELINE (Gemini)")
    print("=" * 60)
    print(f"  Input  : {Path(ORIGINAL_TEMPLATE_PATH).name}")
    print(f"  Output : {Path(FINAL_FIXED_PATH).name}")
    print("=" * 60)
    start_time = time.time()

    with open(ORIGINAL_TEMPLATE_PATH) as f:
        current_template = f.read()

    template_type   = detect_template_type(current_template)
    seen_errors     = set()
    total_fixes     = 0
    all_error_types = []
    total_errors    = 0
    exp_id          = f"EXP{int(time.time())}"

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n[Iteration {iteration}] Running cfn-lint...")
        lint_output, return_code = run_cfn_lint(current_template)

        if return_code == 0:
            save_success(current_template, total_fixes, total_errors,
                        all_error_types, start_time, template_type, exp_id)
            return True

        errors = parse_errors(lint_output)
        errors_only = [e for e in errors if e["severity"] == "ERROR"]

        if not errors_only:
            print("   Only warnings remain — valid for deployment!")
            save_success(current_template, total_fixes, total_errors,
                        all_error_types, start_time, template_type, exp_id,
                        note=f"{total_fixes} iterations — warnings only")
            return True

        for e in errors_only:
            print(f"   [ERROR] {e['message'][:100]}")
            all_error_types.append(e["type"])
        total_errors += len(errors_only)

        error_fingerprint = frozenset(e["message"][:100] for e in errors_only)
        if error_fingerprint in seen_errors:
            elapsed = time.time() - start_time
            print("\n  SAME ERRORS — Escalating!")
            record = make_record(exp_id, template_type, MODEL_NAME,
                                 first_pass=False, iterations=total_fixes,
                                 errors_found=total_errors, error_types=list(set(all_error_types)),
                                 final_status="ESCALATED", time_seconds=elapsed,
                                 aws_cost_saved=0.0, notes="Same error repeated")
            add_result(record)
            return False
        seen_errors.add(error_fingerprint)

        print(f"\n   Sending {len(errors_only)} error(s) to Gemini...")
        fixed_template = call_ai(build_reprompt(current_template, errors_only, iteration))
        current_template = clean_template(fixed_template)
        total_fixes += 1
        print(f"   Iteration {iteration} fixed (memory only)")

    elapsed = time.time() - start_time
    record = make_record(exp_id, template_type, MODEL_NAME,
                         first_pass=False, iterations=total_fixes,
                         errors_found=total_errors, error_types=list(set(all_error_types)),
                         final_status="FAILED", time_seconds=elapsed,
                         aws_cost_saved=0.0, notes="Max iterations reached")
    add_result(record)
    print("\n Max iterations reached.")
    return False

if __name__ == "__main__":
    if "GEMINI_API_KEY" not in os.environ:
        print("ERROR: GEMINI_API_KEY not set!")
        print("Run: export GEMINI_API_KEY='AIza-xxxxxxxxxx'")
        sys.exit(1)
    result = run_pipeline()
    sys.exit(0 if result else 1)
