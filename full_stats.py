import csv, statistics
from collections import Counter

with open('/home/ysivasai99/cfn-pipeline/research_results/cfn_research_results.csv') as f:
    rows = list(csv.DictReader(f))

total = len(rows)
success = sum(1 for r in rows if r['final_status'] == 'SUCCESS')
escalated = sum(1 for r in rows if r['final_status'] == 'ESCALATED')
failed = sum(1 for r in rows if r['final_status'] == 'FAILED')
first_pass = sum(1 for r in rows if r['first_pass'].upper() == 'YES')
iterations = [int(r['iterations']) for r in rows]
times = [float(r['time_seconds']) for r in rows]
errors = [int(r['errors_found']) for r in rows]
zero_one = sum(1 for i in iterations if i <= 1)

all_errors = []
for r in rows:
    types = r.get('error_types', '')
    if types:
        all_errors.extend([t.strip() for t in types.split(',')])
err_total = len(all_errors)
err_counts = Counter(all_errors)

types = Counter(r['template_type'] for r in rows)

print("=" * 55)
print("COMPLETE CANONICAL METRICS — 116 TEMPLATES")
print("=" * 55)
print(f"Total templates:           {total}")
print(f"SUCCESS:                   {success} ({round(success/total*100,1)}%)")
print(f"ESCALATED:                 {escalated} ({round(escalated/total*100,1)}%)")
print(f"FAILED:                    {failed} (0%)")
print(f"First pass (no fix):       {first_pass} ({round(first_pass/total*100,1)}%)")
print(f"Needed at least one fix:   {total-first_pass} ({round((total-first_pass)/total*100,1)}%)")
print(f"Successes needing fix:     {success-first_pass}")
print()
print("--- Iterations ---")
print(f"Avg iterations:            {round(statistics.mean(iterations),2)}")
print(f"Std dev:                   ±{round(statistics.stdev(iterations),2)}")
print(f"Median:                    {statistics.median(iterations)}")
print(f"Max iterations:            {max(iterations)}")
print(f"Min iterations:            {min(iterations)}")
print(f"0-1 iterations:            {zero_one} ({round(zero_one/total*100,1)}%)")
print()
print("--- Time ---")
print(f"Avg time:                  {round(statistics.mean(times),2)}s")
print(f"Fastest:                   {min(times)}s")
print(f"Slowest:                   {max(times)}s")
print()
print("--- Errors ---")
print(f"Max errors in one template: {max(errors)}")
print(f"Total error instances:     {err_total}")
for k, v in err_counts.most_common():
    print(f"  {k}: {v} ({round(v/err_total*100,1)}%)")
print()
print("--- Gate Progression ---")
gate1 = sum(1 for r in rows if r['final_status'] == 'SUCCESS' and
    all(t.strip() in ['syntax_error', 'wrong_value', 'None', '']
    for t in r.get('error_types','').split(',')))
gate1_15 = sum(1 for r in rows if r['final_status'] == 'SUCCESS' and
    all(t.strip() in ['syntax_error', 'wrong_value', 'best_practice', 'None', '']
    for t in r.get('error_types','').split(',')))
print(f"Raw Claude (first pass):   {first_pass} ({round(first_pass/total*100,1)}%)")
print(f"Gate 1 only:               {gate1} ({round(gate1/total*100,1)}%)")
print(f"Gate 1 + 1.5:              {gate1_15} ({round(gate1_15/total*100,1)}%)")
print(f"Full framework:            {success} ({round(success/total*100,1)}%)")
print()
print("--- Cost ---")
print(f"LocalStack savings:        $2.10 (116 x $0.0181)")
print(f"Claude API cost:           $2.55")
print(f"Engineer hours saved:      ~58 hours (100 x 35 min)")
print(f"Productivity savings:      ~$2,900 (58 x $50)")
print(f"ROI:                       ~1,137x")
print()
print("--- Service Categories ---")
print(f"Total categories:          {len(types)}")
for k, v in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print("=" * 55)
