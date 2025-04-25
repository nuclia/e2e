from pathlib import Path
from tabulate import tabulate

import json

results_dir = Path("./results")
timings_data = {}
versions_data = {}
descriptions = {}

# Collect all results
for file in results_dir.rglob("*.json"):
    name = file.stem
    if "__timings" in name:
        key = name.replace("__timings", "")
        with Path(file).open() as f:
            data = json.load(f)
            timings_data[key] = {k: float(v["elapsed"]) for k, v in data.items()}
            for k, v in data.items():
                descriptions[k] = v["desc"]
    elif "__versions" in name:
        key = name.replace(":versions", "")
        with Path(file).open() as f:
            versions_data[key] = json.load(f)

# Build timings table
timing_keys = sorted({k for v in timings_data.values() for k in v})
timing_rows = []

for env_zone in sorted(timings_data):
    row = [env_zone] + [
        f'{timings_data[env_zone].get(k, "-"):.3f}' if k in timings_data[env_zone] else "-"
        for k in timing_keys
    ]
    timing_rows.append(row)

timing_table = tabulate(timing_rows, headers=["Env/Zone"] + timing_keys, tablefmt="github")

# Build version table
version_keys = sorted({k for v in versions_data.values() for k in v})
version_rows = []

for env_zone in sorted(versions_data):
    row = [env_zone] + [versions_data[env_zone].get(k, "-") for k in version_keys]
    version_rows.append(row)

version_table = tabulate(version_rows, headers=["Env/Zone"] + version_keys, tablefmt="github")

# Write summary
with Path("benchmark_summary.md").open("w") as f:
    f.write("### 🧪 Benchmark Timings\n")
    f.write(timing_table + "\n\n")

    f.write("#### 🗒️ Description of timings\n")
    for key in timing_keys:
        f.write(f"- `{key}`: {descriptions.get(key, '')}\n")
    f.write("\n")

    f.write("### 🔢 Component Versions\n")
    f.write(version_table + "\n")
