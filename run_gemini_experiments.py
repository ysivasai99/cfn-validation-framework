import subprocess
import sys
import os
from pathlib import Path

TEMPLATES_DIR = Path("/home/ysivasai99/cfn-pipeline/templates")
PIPELINE      = "/home/ysivasai99/cfn-pipeline/pipeline_gemini.py"

templates = sorted(TEMPLATES_DIR.glob("*.yaml"))
total     = len(templates)
success   = 0
failed    = 0

print("=" * 60)
print(f"  GEMINI BATCH EXPERIMENTS — {total} templates")
print("=" * 60)

for i, template in enumerate(templates, 1):
    print(f"\n[{i}/{total}] {template.name}")
    print("-" * 40)
    env = {**os.environ, "CFN_TEMPLATE_PATH": str(template)}
    result = subprocess.run([sys.executable, PIPELINE], env=env)
    if result.returncode == 0:
        success += 1
    else:
        failed += 1

print("\n" + "=" * 60)
print(f"  BATCH COMPLETE")
print(f"  SUCCESS  : {success}")
print(f"  FAILED   : {failed}")
print(f"  Total    : {total}")
print("=" * 60)
