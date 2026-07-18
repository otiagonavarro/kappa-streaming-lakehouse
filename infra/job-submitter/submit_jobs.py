#!/usr/bin/env python3
"""Submit PyFlink jobs to the standalone Flink cluster via flink run --detached."""

import contextlib
import os
import subprocess
import sys
import time

import requests

FLINK_HOST = os.environ.get("FLINK_JOBMANAGER_HOST", "jobmanager")
FLINK_PORT = os.environ.get("FLINK_JOBMANAGER_PORT", "8081")
FLINK_RPC_PORT = "6123"
FLINK_API = f"http://{FLINK_HOST}:{FLINK_PORT}"
FLINK_HOME = os.environ.get("FLINK_HOME", "/opt/flink")

JOBS = [
    ("Bronze: Raw Event Ingestion",  "jobs/raw_event_ingestion.py"),
    ("Silver: Event Enrichment",      "jobs/silver_enrichment.py"),
    ("Gold: Session Aggregation",     "jobs/session_aggregation.py"),
    ("Gold: Product Funnel",          "jobs/product_funnel.py"),
    ("Gold: User 360",                "jobs/user_360.py"),
]


def wait_for_flink(timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with contextlib.suppress(requests.RequestException):
            resp = requests.get(f"{FLINK_API}/overview", timeout=5)
            if resp.status_code == 200 and resp.json().get("taskmanagers", 0) > 0:
                print(f"Flink ready: {resp.json()['taskmanagers']} TaskManager(s) online")
                return
        print("Waiting for Flink cluster…")
        time.sleep(5)
    raise TimeoutError(f"Flink cluster not ready after {timeout}s")


def submit_job(name: str, script_path: str, from_beginning: bool = False) -> str:
    cmd = [
        f"{FLINK_HOME}/bin/flink", "run",
        "--detached",
        "-D", f"jobmanager.rpc.address={FLINK_HOST}",
        "-D", f"jobmanager.rpc.port={FLINK_RPC_PORT}",
        "-D", f"rest.address={FLINK_HOST}",
        "-D", f"rest.port={FLINK_PORT}",
        "-D", "python.client.executable=python3",
        "-D", "python.executable=python3",
        "-py", script_path,
        "-pyfs", "jobs/",
        "-pyfs", "/app",
    ]
    if from_beginning:
        cmd.append("--from-beginning")
    print(f"Submitting: {name} ({script_path})")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(f"{name} submission failed:\n{output}")
    job_id = next((line.strip().split()[-1] for line in output.splitlines() if "JobID" in line), "")
    print(f"  ✓ {name} submitted" + (f" (JobID: {job_id})" if job_id else ""))
    return job_id


def monitor_jobs(job_ids: list[str]) -> None:
    print(f"Monitoring {len(job_ids)} job(s) via Flink REST API…")
    while True:
        with contextlib.suppress(requests.RequestException):
            resp = requests.get(f"{FLINK_API}/jobs", timeout=5)
            if resp.status_code == 200:
                jobs = {j["id"]: j["status"] for j in resp.json().get("jobs", [])}
                for jid in job_ids:
                    status = jobs.get(jid, "UNKNOWN")
                    if status in ("FAILED", "CANCELED"):
                        print(f"WARNING: job {jid} is {status}", file=sys.stderr)
        time.sleep(30)


def main() -> int:
    from_beginning = "--from-beginning" in sys.argv
    print("=== Kappa Job Submitter ===")
    try:
        wait_for_flink()
    except TimeoutError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    job_ids: list[str] = []
    for name, script in JOBS:
        try:
            if job_id := submit_job(name, script, from_beginning):
                job_ids.append(job_id)
            time.sleep(3)
        except Exception as exc:
            print(f"ERROR submitting {name}: {exc}", file=sys.stderr)
            return 1

    print("All jobs submitted.")
    try:
        monitor_jobs(job_ids)
    except KeyboardInterrupt:
        print("Shutting down…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
