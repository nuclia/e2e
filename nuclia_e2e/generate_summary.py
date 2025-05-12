from pathlib import Path
from tabulate import tabulate
import urllib.parse
import json
import datetime
from datetime import datetime, timezone, timedelta


results_dir = Path("./results")
timings_data = {}
versions_data = {}
descriptions = {}


def generate_last_upload_trace_url(base_url: str, cluster_name: str, kbid: str, tempo_datasource: str) -> str:
    """
    Using the PATCH tusupload as a reference of the request that will contain the /processing/push
    """
    # Compute the time range: last 1 hour
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # Format to ISO8601 with Zulu time (UTC)
    from_str = one_hour_ago.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    to_str = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    traceql_query = (
        f'{{resource.k8s.cluster="{cluster_name}" '
        f'&& span.http.method="POST" '
        f'&& span.http.url=~".*{kbid}.*"}}'
    )

    payload = {
        "datasource": "P95F6455D1776E941",  # Customize if needed
        "queries": [{"refId": "A", "query": traceql_query}],
        "range": {"from": from_str, "to": to_str},
    }

    left_param = urllib.parse.quote(json.dumps(payload))
    return f"{base_url}?orgId=1&left={left_param}"


if __name__ == "__main__":
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

    # Build trace links table
    grafana_rows = []
    for file in results_dir.rglob("*__ids.json"):
        env_zone = file.stem.replace("__ids", "")
        env, zone = env_zone.split("__", 1)
        with open(file) as f:
            ids = json.load(f)
        url = generate_last_upload_trace_url(
            base_url=ids["grafana_url"],
            cluster_name=zone,
            kbid=ids["kbid"],
            tempo_datasource=ids["tempo_datasource_id"],
        )
        grafana_rows.append((env, zone, f"[View processing push Trace]({url})"))

    grafana_table = tabulate(grafana_rows, headers=["Env", "Zone", "Tempo Trace"], tablefmt="github")

    # Write summary
    with Path("benchmark_summary.md").open("w") as f:
        f.write("### 🧪 Benchmark Timings\n")
        f.write(timing_table + "\n\n")

        f.write("#### 🗒️ Description of timings\n")
        for key in timing_keys:
            f.write(f"- `{key}`: {descriptions.get(key, '')}\n")
        f.write("\n")

        f.write("\n### 🔍 Trace Links\n")
        f.write(
            "\nThis traces correspond to the nucliadb call that sends to process the file. Any processing attempt trace will be linked as the last span named 'Processing attempt #1'\n"
        )
        f.write(grafana_table + "\n")

        f.write("### 🔢 Component Versions\n")
        f.write(version_table + "\n")
