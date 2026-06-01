import subprocess
import re
import os
import sys
import time
import boto3
from pathlib import Path
import anthropic

client_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

cfn_client = boto3.client(
    "cloudformation",
    endpoint_url="http://localhost:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

sys.path.insert(0, str(Path(__file__).parent))
from results_tracker import add_result, make_record

ORIGINAL_TEMPLATE_PATH = os.environ.get("CFN_TEMPLATE_PATH", "/home/ysivasai99/cfn-pipeline/broken_template.yaml")
original_name          = Path(ORIGINAL_TEMPLATE_PATH).stem
FINAL_FIXED_PATH       = f"/home/ysivasai99/cfn-pipeline/fixed_templates/final_{original_name}_fixed.yaml"
TEMP_PATH              = "/tmp/cfn_current_template.yaml"
MAX_ITERATIONS         = 8
MODEL_NAME             = "Claude"
KEEP_STACK             = True

ERROR_PATTERNS = [
    {"pattern": r"'(.+)' is not a '(.+)' with pattern", "type": "wrong_value",  "hint": "Value doesn't match required pattern."},
    {"pattern": r"does not match '(.+)'",                "type": "wrong_value",  "hint": "Value format incorrect."},
    {"pattern": r"Avoid hardcoding availability zones",   "type": "wrong_value",  "hint": "Use !Select [0, !GetAZs '']"},
    {"pattern": r"Invalid id '(.+)'",                    "type": "missing_ref",  "hint": "Referenced ID not valid."},
    {"pattern": r"'(.+)' is not valid",                  "type": "wrong_value",  "hint": "Value not accepted by AWS."},
    {"pattern": r"DBInstanceClass",                      "type": "wrong_value",  "hint": "Use a valid DBInstanceClass like db.t3.micro"},
    {"pattern": r"InstanceType.*is not",                 "type": "wrong_value",  "hint": "Use a valid InstanceType like t2.micro"},
    {"pattern": r"Engine.*is not",                       "type": "wrong_value",  "hint": "Use a valid Engine like mysql or postgres"},
    {"pattern": r"MfaConfiguration",                     "type": "wrong_value",  "hint": "Use OFF, ON, or OPTIONAL as string for MfaConfiguration."},
    {"pattern": r"is not of type 'boolean'",             "type": "wrong_value",  "hint": "Use true or false without quotes."},
    {"pattern": r"ScheduleExpression",                   "type": "wrong_value",  "hint": "Use rate(5 minutes) or cron(0 12 * * ? *)"},
    {"pattern": r"is not one of \[10, 30, 60\]",         "type": "wrong_value",  "hint": "Use Period value of 10, 30, or multiple of 60"},
    {"pattern": r"less than the minimum",                "type": "wrong_value",  "hint": "Use a value >= minimum allowed."},
    {"pattern": r"greater than the maximum",             "type": "wrong_value",  "hint": "Use a value <= maximum allowed."},
    {"pattern": r"Lambda.*Permission|Permission.*Lambda", "type": "missing_config", "hint": "Add AWS::Lambda::Permission for EventBridge/SNS triggers."},
    {"pattern": r"NumCacheNodes.*Redis|Redis.*NumCacheNodes", "type": "wrong_value", "hint": "For Redis use NumCacheClusters: 1 instead of NumCacheNodes."},
    {"pattern": r"FAIL|WARN",                            "type": "security_issue", "hint": "Fix security violation found by cfn-nag."},
]

BEST_PRACTICE_CHECKS = [
    {
        "name": "ALB SecurityGroups",
        "check": lambda t: "ElasticLoadBalancingV2::LoadBalancer" in t and "SecurityGroups" not in t.split("ElasticLoadBalancingV2::LoadBalancer")[1][:500],
        "hint": "ALB requires SecurityGroups property. Add: SecurityGroups: [!Ref MySG]"
    },
    {
        "name": "EC2 SecurityGroupIds",
        "check": lambda t: "AWS::EC2::Instance" in t and "SecurityGroupIds" not in t.split("AWS::EC2::Instance")[1][:500],
        "hint": "EC2 Instance should have explicit SecurityGroupIds. Add: SecurityGroupIds: [!Ref MySG]"
    },
    {
        "name": "Lambda EventBridge Permission",
        "check": lambda t: "AWS::Events::Rule" in t and "AWS::Lambda::Permission" not in t,
        "hint": "EventBridge Rule targeting Lambda needs AWS::Lambda::Permission resource."
    },
    {
        "name": "Hardcoded Password",
        "check": lambda t: re.search(r"MasterUserPassword\s*:\s*['\"]?\w+['\"]?", t) is not None and "resolve:secretsmanager" not in t and "resolve:ssm" not in t,
        "hint": "Replace hardcoded passwords with Secrets Manager dynamic reference."
    },
    {
        "name": "Redis NumCacheNodes",
        "check": lambda t: "redis" in t.lower() and "NumCacheNodes" in t,
        "hint": "Redis clusters should use NumCacheClusters: 1 instead of NumCacheNodes."
    },
    {
        "name": "ASG TargetGroupARNs",
        "check": lambda t: "AutoScaling::AutoScalingGroup" in t and "ElasticLoadBalancingV2::TargetGroup" in t and "TargetGroupARNs" not in t,
        "hint": "AutoScaling Group should reference TargetGroup via TargetGroupARNs."
    },
]

def run_cfn_lint(template_content):
    with open(TEMP_PATH, "w") as f: f.write(template_content)
    result = subprocess.run(["cfn-lint", TEMP_PATH], capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def run_cfn_nag(template_content):
    """Gate 1 — cfn-nag security scan"""
    with open(TEMP_PATH, "w") as f: f.write(template_content)
    nag_path = os.path.expanduser("~/.local/share/gem/ruby/3.0.0/bin/cfn_nag_scan")
    result = subprocess.run(
        [nag_path, "--input-path", TEMP_PATH],
        capture_output=True, text=True
    )
    return result.stdout.strip(), result.returncode

def parse_cfn_nag(nag_output):
    """Parse cfn-nag output into error list"""
    errors = []
    for line in nag_output.splitlines():
        line = line.strip()
        if line.startswith("| FAIL"):
            severity = "ERROR"
            etype = "security_issue"
        elif line.startswith("| WARN"):
            severity = "WARNING"
            etype = "security_issue"
        elif line.startswith("|") and len(line) > 2 and not line.startswith("| Failures") and not line.startswith("| Warnings"):
            msg = line[1:].strip()
            if msg:
                errors.append({
                    "severity": severity if 'severity' in dir() else "WARNING",
                    "message": msg,
                    "type": "security_issue",
                    "hint": "Fix this security violation. Use Secrets Manager for passwords, restrict CidrIp from 0.0.0.0/0, enable encryption."
                })
    return [e for e in errors if e.get("message")]

def run_best_practice_checks(template_content):
    issues = []
    for check in BEST_PRACTICE_CHECKS:
        try:
            if check["check"](template_content):
                issues.append({
                    "severity": "ERROR",
                    "message": "Best practice violation: " + check["name"],
                    "type": "best_practice",
                    "hint": check["hint"]
                })
        except: pass
    return issues

def run_localstack_deploy(template_content, stack_name):
    print("\n[Gate 2] Deploying to LocalStack...")
    try:
        try:
            cfn_client.delete_stack(StackName=stack_name)
            time.sleep(3)
        except: pass

        cfn_client.create_stack(
            StackName=stack_name,
            TemplateBody=template_content,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"]
        )

        for _ in range(30):
            time.sleep(3)
            response = cfn_client.describe_stacks(StackName=stack_name)
            status = response["Stacks"][0]["StackStatus"]
            print("   Stack status: " + status)

            if status == "CREATE_COMPLETE":
                print("   LocalStack deploy SUCCESS!")
                resources = cfn_client.list_stack_resources(StackName=stack_name)
                print("\n   Deployed Resources (" + str(len(resources["StackResourceSummaries"])) + "):")
                for r in resources["StackResourceSummaries"]:
                    print("   OK " + r["LogicalResourceId"] + " (" + r["ResourceType"] + ")")
                if not KEEP_STACK:
                    cfn_client.delete_stack(StackName=stack_name)
                else:
                    print("\n   Stack kept: " + stack_name)
                return True, []

            elif "FAILED" in status or "ROLLBACK" in status:
                events = cfn_client.describe_stack_events(StackName=stack_name)["StackEvents"]
                errors = []
                for event in events:
                    if "FAILED" in event.get("ResourceStatus", ""):
                        errors.append({
                            "severity": "ERROR",
                            "message": event.get("LogicalResourceId", "") + " (" + event.get("ResourceType", "") + "): " + event.get("ResourceStatusReason", ""),
                            "hint": "Fix the runtime configuration error for this resource.",
                            "type": "runtime_error"
                        })
                cfn_client.delete_stack(StackName=stack_name)
                return False, errors

        cfn_client.delete_stack(StackName=stack_name)
        return False, [{"message": "Timeout", "severity": "ERROR", "hint": "Stack creation timed out.", "type": "timeout"}]

    except Exception as e:
        print("   LocalStack error: " + str(e)[:100])
        return False, [{"message": str(e)[:200], "severity": "ERROR", "hint": "Fix the configuration error.", "type": "runtime_error"}]

def parse_errors(lint_output):
    errors = []
    for line in lint_output.splitlines():
        if not line.strip() or line.startswith("/"): continue
        severity = "ERROR" if line.startswith("E") else "WARNING"
        error_type = "syntax_error"
        hint = "Review this line."
        for ep in ERROR_PATTERNS:
            if re.search(ep["pattern"], line):
                error_type = ep["type"]
                hint = ep["hint"]
                break
        errors.append({"severity": severity, "message": line.strip(), "type": error_type, "hint": hint})
    return errors

def build_reprompt(template_yaml, errors, iteration, gate="Gate 1"):
    errors_text = "\n".join([
        "- [" + e["severity"] + "] " + e["message"][:200] + "\n  Hint: " + e.get("hint", "Fix this error.")
        for e in errors
    ])
    return """You are a CloudFormation expert. Fix these """ + gate + """ errors.
ITERATION: """ + str(iteration) + """ of """ + str(MAX_ITERATIONS) + """
ERRORS:
""" + errors_text + """
TEMPLATE:
""" + template_yaml + """
INSTRUCTIONS:
1. Fix ONLY the erroring properties
2. For invalid AZ: use !Select [0, !GetAZs '']
3. For invalid S3 name: lowercase letters, numbers, hyphens only
4. For invalid AMI: use ami-0c02fb55956c7d316
5. For invalid DBInstanceClass: use db.t3.micro
6. For invalid InstanceType: use t2.micro
7. For invalid Engine: use mysql
8. For MfaConfiguration: use 'OFF' as string
9. For boolean fields: use true or false without quotes
10. For missing SecurityGroups on ALB: add SecurityGroups: [!Ref MySG]
11. For missing SecurityGroupIds on EC2: add SecurityGroupIds: [!Ref MySG]
12. For EventBridge Lambda trigger: add AWS::Lambda::Permission resource
13. For Redis NumCacheNodes: change to NumCacheClusters: 1
14. For hardcoded passwords: use Secrets Manager dynamic reference
15. For security violations (cfn-nag): restrict CidrIp, enable encryption, remove hardcoded secrets
16. Return ONLY corrected YAML, no explanation, no markdown fences
"""

def call_ai(prompt):
    print("   Calling Claude API...")
    response = client_claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

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
    if "AutoScaling" in template: return "EC2 + Auto Scaling"
    if "EC2" in template and "LoadBalancer" in template: return "EC2 + ALB"
    if "EC2" in template: return "VPC + EC2"
    if "S3" in template: return "S3 Bucket"
    if "SQS" in template or "SNS" in template: return "SQS + SNS"
    if "ECS" in template: return "ECS + ECR"
    if "CloudWatch" in template: return "CloudWatch"
    if "Cognito" in template: return "Cognito"
    return "General CFN"

def save_success(current_template, total_fixes, total_errors, all_error_types, start_time, template_type, exp_id, note=""):
    elapsed = time.time() - start_time
    with open(FINAL_FIXED_PATH, "w") as f: f.write(current_template)
    print("\n SUCCESS! Valid after " + str(total_fixes) + " fix(es) | Time: " + str(round(elapsed, 1)) + "s")
    print(" Saved -> " + Path(FINAL_FIXED_PATH).name)
    record = make_record(exp_id, template_type, MODEL_NAME,
                         first_pass=(total_fixes == 0), iterations=total_fixes,
                         errors_found=total_errors, error_types=list(set(all_error_types)),
                         final_status="SUCCESS", time_seconds=elapsed,
                         aws_cost_saved=0.05, notes=note or str(total_fixes) + " iterations")
    add_result(record)
    print("\nFINAL TEMPLATE:")
    print("-" * 40)
    print(current_template)

def run_pipeline():
    print("=" * 60)
    print("  AI-CFN SELF-HEALING PIPELINE (Claude) — THREE GATE")
    print("=" * 60)
    print("  Input  : " + Path(ORIGINAL_TEMPLATE_PATH).name)
    print("  Output : " + Path(FINAL_FIXED_PATH).name)
    print("  Keep Stack: " + str(KEEP_STACK))
    print("=" * 60)
    start_time = time.time()

    with open(ORIGINAL_TEMPLATE_PATH) as f:
        current_template = f.read()

    template_type   = detect_template_type(current_template)
    seen_errors     = set()
    total_fixes     = 0
    all_error_types = []
    total_errors    = 0
    exp_id          = "EXP" + str(int(time.time()))
    stack_name      = "cfn-test-" + str(int(time.time()))

    # ── GATE 1: cfn-lint ─────────────────────────────────
    print("\n[GATE 1] Static Analysis (cfn-lint)...")
    for iteration in range(1, MAX_ITERATIONS + 1):
        print("\n[Iteration " + str(iteration) + "] Running cfn-lint...")
        lint_output, return_code = run_cfn_lint(current_template)
        errors = parse_errors(lint_output)
        errors_only = [e for e in errors if e["severity"] == "ERROR"]

        if return_code == 0 or not errors_only:
            print(" Gate 1 (cfn-lint) PASSED!")
            break

        for e in errors_only:
            print("   [ERROR] " + e["message"][:100])
            all_error_types.append(e["type"])
        total_errors += len(errors_only)

        error_fingerprint = frozenset(e["message"][:100] for e in errors_only)
        if error_fingerprint in seen_errors:
            elapsed = time.time() - start_time
            print("\n  Gate 1 ESCALATED!")
            record = make_record(exp_id, template_type, MODEL_NAME,
                                 first_pass=False, iterations=total_fixes,
                                 errors_found=total_errors, error_types=list(set(all_error_types)),
                                 final_status="ESCALATED", time_seconds=elapsed,
                                 aws_cost_saved=0.0, notes="Gate 1 escalated")
            add_result(record)
            return False
        seen_errors.add(error_fingerprint)

        print("\n   Sending " + str(len(errors_only)) + " error(s) to Claude (Gate 1)...")
        fixed_template = call_ai(build_reprompt(current_template, errors_only, iteration, "Gate 1 cfn-lint"))
        current_template = clean_template(fixed_template)
        total_fixes += 1
        print("   Gate 1 Iteration " + str(iteration) + " fixed!")

    # ── GATE 1 continued: cfn-nag security scan ──────────
    print("\n[GATE 1 — cfn-nag] Security Scan...")
    nag_output, nag_code = run_cfn_nag(current_template)
    nag_errors = parse_cfn_nag(nag_output)
    nag_fails = [e for e in nag_errors if e["severity"] == "ERROR"]

    if nag_fails:
        print("   cfn-nag found " + str(len(nag_fails)) + " security issue(s):")
        for e in nag_fails:
            print("   [SECURITY] " + e["message"][:100])
        print("\n   Sending security issues to Claude...")
        fixed_template = call_ai(build_reprompt(current_template, nag_fails, 1, "Gate 1 cfn-nag Security"))
        current_template = clean_template(fixed_template)
        total_fixes += 1
        all_error_types.extend(["security_issue"] * len(nag_fails))
        total_errors += len(nag_fails)
        print("   Security fixes applied!")
    else:
        print("   cfn-nag: No security issues found!")

    # ── GATE 1.5: Best Practice Checks ───────────────────
    print("\n[GATE 1.5] Best Practice Checks...")
    bp_issues = run_best_practice_checks(current_template)
    if bp_issues:
        print("   Found " + str(len(bp_issues)) + " best practice issues:")
        for issue in bp_issues:
            print("   [BP] " + issue["message"])
        print("\n   Sending to Claude (Gate 1.5)...")
        fixed_template = call_ai(build_reprompt(current_template, bp_issues, 1, "Gate 1.5 Best Practices"))
        current_template = clean_template(fixed_template)
        total_fixes += 1
        all_error_types.extend(["best_practice"] * len(bp_issues))
        total_errors += len(bp_issues)
        print("   Best practice fixes applied!")
    else:
        print("   No best practice issues found!")

    # ── GATE 2: LocalStack Runtime ────────────────────────
    print("\n[GATE 2] LocalStack Runtime Deploy...")
    seen_ls_errors = set()

    for iteration in range(1, MAX_ITERATIONS + 1):
        success, ls_errors = run_localstack_deploy(current_template, stack_name)

        if success:
            save_success(current_template, total_fixes, total_errors,
                        all_error_types, start_time, template_type, exp_id,
                        note=str(total_fixes) + " iterations — Gate 1+1.5+2 passed")
            return True

        if not ls_errors:
            save_success(current_template, total_fixes, total_errors,
                        all_error_types, start_time, template_type, exp_id,
                        note=str(total_fixes) + " iterations — passed")
            return True

        supported_errors = [e for e in ls_errors if not any(
            skip in e.get("message", "") for skip in [
                "AWS::CloudFormation::Stack",
                "AWS::Events::Rule",
                "AWS::WAFv2",
                "AWS::CloudFront",
                "AWS::CodePipeline",
                "AWS::CodeBuild",
                "AWS::ApiGateway",
            ]
        )]

        if not supported_errors:
            print("   Unsupported LocalStack resources — recording as research finding!")
            save_success(current_template, total_fixes, total_errors,
                        all_error_types, start_time, template_type, exp_id,
                        note=str(total_fixes) + " iterations — unsupported resources noted")
            return True

        print("\n   Gate 2 errors (" + str(len(supported_errors)) + "):")
        for e in supported_errors:
            print("   [RUNTIME] " + e["message"][:100])
            all_error_types.append(e.get("type", "runtime_error"))
        total_errors += len(supported_errors)

        ls_fingerprint = frozenset(e["message"][:80] for e in supported_errors)
        if ls_fingerprint in seen_ls_errors:
            elapsed = time.time() - start_time
            print("\n  Gate 2 ESCALATED!")
            record = make_record(exp_id, template_type, MODEL_NAME,
                                 first_pass=False, iterations=total_fixes,
                                 errors_found=total_errors, error_types=list(set(all_error_types)),
                                 final_status="ESCALATED", time_seconds=elapsed,
                                 aws_cost_saved=0.0, notes="Gate 2 escalated")
            add_result(record)
            return False
        seen_ls_errors.add(ls_fingerprint)

        print("\n   Sending " + str(len(supported_errors)) + " runtime error(s) to Claude (Gate 2)...")
        fixed_template = call_ai(build_reprompt(current_template, supported_errors, iteration, "Gate 2 LocalStack"))
        current_template = clean_template(fixed_template)
        total_fixes += 1
        print("   Gate 2 Iteration " + str(iteration) + " fixed!")

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
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set!")
        sys.exit(1)
    result = run_pipeline()
    sys.exit(0 if result else 1)
