# Update the CI reference trigger log and merge it into Mu2e/mu2e-trig-config
#
# The new log comes from one of:
#   --local      : run test/triggerTest.fcl on ci/data_files.txt (requires a muse setup
#                  with mu2e-trig-config built, since the fcl includes the generated menus)
#   --url <URL>  : a CI log, e.g. .../mu2e-offline-build-test/<N>/artifact/trigger.log
# Text after the art exit status line is trimmed (the CI log appends the comparison report).
#
# A PR is opened from a fresh branch of upstream main (in a temporary git worktree, so the
# current checkout is untouched). With --merge, once the required checks pass and the PR has
# no conflicts, it is merged with --admin, bypassing the review requirement.

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime

UPSTREAM = "Mu2e/mu2e-trig-config"
REFERENCE = "ci/reference_log_file.log"
ART_EXIT = re.compile(r"^Art has completed and will exit with status (\d+)\.")


# --------------------------------------------------------------
# Run a command, echoing it, and return its stdout
def run(cmd, cwd=None, check=True):
    print("+ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        sys.exit("Command failed with status %i" % result.returncode)
    return result.stdout.strip()


# --------------------------------------------------------------
# Trim a log after the art exit status line, requiring a clean exit
def trim_log(text):
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = ART_EXIT.match(line)
        if match:
            if match.group(1) != "0":
                sys.exit("Art exited with status %s, not updating the reference" % match.group(1))
            return "".join(lines[: index + 1])
    sys.exit("No art exit status line found in the log, not updating the reference")


# --------------------------------------------------------------
# Produce the log by running the trigger test locally
def make_local_log(repo, workdir):
    if shutil.which("mu2e") is None:
        sys.exit("mu2e is not on PATH: set up a muse build including mu2e-trig-config first")
    env = dict(os.environ)
    for var in ["OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"]:
        env[var] = "1"
    log_path = os.path.join(workdir, "local_trigger_results.log")
    cmd = [
        "mu2e", "-c", os.path.join(repo, "test", "triggerTest.fcl"),
        "-S", os.path.join(repo, "ci", "data_files.txt"),
        "-n", "-1", "--nthreads", "1", "--nschedules", "1",
    ]
    print("+ " + " ".join(cmd) + " > " + log_path)
    with open(log_path, "w") as f:
        status = subprocess.run(cmd, cwd=workdir, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    if status != 0:
        sys.exit("mu2e failed with status %i, see %s" % (status, log_path))
    with open(log_path) as f:
        return f.read()


# --------------------------------------------------------------
# Download a CI log
def fetch_log(url):
    print("Downloading " + url)
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read().decode("utf-8", errors="replace")


# --------------------------------------------------------------
# Find the remote names for the upstream repository and the user's fork
def find_remotes(repo, login):
    upstream, fork = None, None
    for line in run(["git", "remote", "-v"], cwd=repo).splitlines():
        name, url = line.split()[:2]
        if re.search(r"[:/]%s(\.git)?$" % UPSTREAM, url, re.IGNORECASE):
            upstream = name
        elif re.search(r"[:/]%s/mu2e-trig-config(\.git)?$" % login, url, re.IGNORECASE):
            fork = name
    if upstream is None or fork is None:
        sys.exit("Need remotes for %s and %s/mu2e-trig-config" % (UPSTREAM, login))
    return upstream, fork


# --------------------------------------------------------------
# Wait for GitHub to compute whether the PR can be merged
def wait_mergeable(pr):
    for _ in range(30):
        state = run(["gh", "pr", "view", pr, "-R", UPSTREAM, "--json", "mergeable", "--jq", ".mergeable"])
        if state != "UNKNOWN":
            return state
        time.sleep(10)
    return "UNKNOWN"


# --------------------------------------------------------------
# Main
parser = argparse.ArgumentParser(description="Update the CI reference trigger log in a PR to %s" % UPSTREAM)
source = parser.add_mutually_exclusive_group(required=True)
source.add_argument("--local", action="store_true", help="Run triggerTest.fcl locally to make the log")
source.add_argument("--url", help="URL of a CI trigger log")
parser.add_argument("--workdir", help="Directory for the local job output (default: a new temporary directory)")
parser.add_argument("--merge", action="store_true",
                    help="Merge the PR with --admin once the required checks pass and there are no conflicts")
parser.add_argument("--dry-run", action="store_true", help="Make the log and show the diff stat, without committing")
args = parser.parse_args()

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
workdir = args.workdir or tempfile.mkdtemp(prefix="trig_ref_log_")
os.makedirs(workdir, exist_ok=True)

log = trim_log(make_local_log(repo, workdir) if args.local else fetch_log(args.url))
log_path = os.path.join(workdir, "reference_log_file.log")
with open(log_path, "w") as f:
    f.write(log)

login = run(["gh", "api", "user", "--jq", ".login"])
upstream, fork = find_remotes(repo, login)
run(["git", "fetch", upstream, "main"], cwd=repo)

# Make a worktree on a new branch from upstream main
branch = "CILogUpdate_" + datetime.now().strftime("%Y%m%d_%H%M%S")
worktree = os.path.join(workdir, "worktree")
run(["git", "worktree", "add", "-b", branch, worktree, "%s/main" % upstream], cwd=repo)
try:
    with open(os.path.join(worktree, REFERENCE), "w") as f:
        f.write(log)
    if not run(["git", "status", "--porcelain"], cwd=worktree):
        print("Reference log is unchanged, nothing to do")
        sys.exit(0)
    print(run(["git", "diff", "--stat"], cwd=worktree))
    if args.dry_run:
        print("Dry run: new log written to %s" % log_path)
        sys.exit(0)

    source_text = "a local run of test/triggerTest.fcl" if args.local else args.url
    run(["git", "commit", "-am", "Update reference log"], cwd=worktree)
    run(["git", "push", fork, branch], cwd=worktree)
    pr_url = run(["gh", "pr", "create", "-R", UPSTREAM, "--base", "main", "--head", "%s:%s" % (login, branch),
                  "--title", "Update CI reference log",
                  "--body", "Update `%s` from %s." % (REFERENCE, source_text)])
    print("Opened " + pr_url)
    pr = pr_url.rstrip("/").split("/")[-1]
    if not args.merge:
        sys.exit(0)

    # Wait for the required checks, then merge only if there are no conflicts
    time.sleep(15)
    checks = subprocess.run(["gh", "pr", "checks", pr, "-R", UPSTREAM, "--required", "--watch", "--fail-fast"])
    if checks.returncode != 0:
        sys.exit("Required checks did not pass, not merging %s" % pr_url)
    mergeable = wait_mergeable(pr)
    if mergeable != "MERGEABLE":
        sys.exit("PR is %s, not merging %s" % (mergeable, pr_url))
    run(["gh", "pr", "merge", pr, "-R", UPSTREAM, "--merge", "--admin"])
    run(["git", "push", fork, "--delete", branch], cwd=repo, check=False)
    print("Merged " + pr_url)
finally:
    run(["git", "worktree", "remove", "--force", worktree], cwd=repo, check=False)
    run(["git", "branch", "-D", branch], cwd=repo, check=False)
