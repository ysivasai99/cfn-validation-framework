import os
import subprocess
import time

templates_dir = "/home/ysivasai99/cfn-pipeline/templates"

new_templates = [
    "ecs_fargate_01", "ecs_fargate_02", "ecs_fargate_03", "ecs_fargate_04",
    "ecs_fargate_05", "ecs_fargate_06", "ecs_fargate_07",
    "rds_secrets_01", "rds_secrets_02", "rds_secrets_03", "rds_secrets_04",
    "rds_secrets_05", "rds_secrets_06", "rds_secrets_07",
    "kinesis_s3_01", "kinesis_s3_02", "kinesis_s3_03", "kinesis_s3_04",
    "kinesis_s3_05", "kinesis_s3_06", "kinesis_s3_07",
    "cognito_api_01", "cognito_api_02", "cognito_api_03", "cognito_api_04",
    "cognito_api_05", "cognito_api_06", "cognito_api_07",
    "cloudwatch_sns_01", "cloudwatch_sns_02", "cloudwatch_sns_03", "cloudwatch_sns_04",
    "cloudwatch_sns_05", "cloudwatch_sns_06", "cloudwatch_sns_07",
    "iam_security_01", "iam_security_02", "iam_security_03", "iam_security_04",
    "iam_security_05", "iam_security_06", "iam_security_07",
    "mixed_01", "mixed_02", "mixed_03", "mixed_04",
    "mixed_05", "mixed_06", "mixed_07", "mixed_08",
]

success = failed = 0
for i, name in enumerate(new_templates):
    path = f"{templates_dir}/{name}.yaml"
    print(f"\n[{i+1}/50] Running: {name}")
    print("=" * 50)
    env = os.environ.copy()
    env["CFN_TEMPLATE_PATH"] = path
    result = subprocess.run(
        ["python3", "/home/ysivasai99/cfn-pipeline/pipeline.py"],
        env=env
    )
    if result.returncode == 0:
        success += 1
    else:
        failed += 1
    time.sleep(2)

print("\n" + "=" * 50)
print(f"COMPLETE")
print(f"SUCCESS : {success}")
print(f"FAILED  : {failed}")
print(f"Total   : {success + failed}")
print("=" * 50)
