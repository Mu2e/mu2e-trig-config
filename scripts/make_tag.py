# Make a new tag of Mu2e/mu2e-trig-config
#
# Usage: python scripts/make_tag.py 8.12.00
#
# The version in CMakeLists.txt is updated in a PR to Mu2e/mu2e-trig-config, the PR is merged
# with --admin once the required checks pass, and the merge is tagged (e.g. v8_12_00) as a
# GitHub release. The work is done in a temporary git worktree, so the current checkout is
# untouched.
#
# Checks:
#   - The version must be greater than the latest existing tag, and you are asked to confirm
#     if it skips a major, minor, or patch number
#   - If the current checkout is not at the HEAD of Mu2e main, you are asked whether to tag
#     the current checkout (then the version update commit is tagged) or Mu2e main's HEAD

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

UPSTREAM = "Mu2e/mu2e-trig-config"
CMAKE = "CMakeLists.txt"
CMAKE_VERSION = re.compile(r"(project\s*\(\s*mu2e-trig-config\s+VERSION\s+)(\d+)\.(\d+)\.(\d+)")
TAG = re.compile(r"^v(\d+)_(\d+)_(\d+)$")


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
# Ask a question until one of the allowed (single letter) answers is given
def ask(question, answers):
    while True:
        try:
            answer = input("%s [%s] " % (question, "/".join(answers))).strip().lower()
        except EOFError:
            sys.exit("\nNo answer given, aborting")
        if answer in answers:
            return answer


# --------------------------------------------------------------
# Version formatting
def version_string(version):
    return "%i.%02i.%02i" % version


def tag_name(version):
    return "v%i_%02i_%02i" % version


def parse_version(text):
    match = re.match(r"^v?(\d+)[._](\d+)[._](\d+)$", text.strip())
    if not match:
        sys.exit("Version '%s' is not of the form X.Y.Z (e.g. 8.12.00)" % text)
    return tuple(int(x) for x in match.groups())


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
# Latest version tag in the upstream repository
def latest_tag(repo, upstream):
    versions = []
    for line in run(["git", "ls-remote", "--tags", upstream], cwd=repo).splitlines():
        ref = line.split()[1]
        if ref.endswith("^{}"):
            continue
        match = TAG.match(ref.replace("refs/tags/", ""))
        if match:
            versions.append(tuple(int(x) for x in match.groups()))
    if not versions:
        sys.exit("No version tags found in %s" % UPSTREAM)
    return max(versions)


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
parser = argparse.ArgumentParser(description="Update the version and make a new tag of %s" % UPSTREAM)
parser.add_argument("version", help="New version, e.g. 8.12.00 (tagged as v8_12_00)")
parser.add_argument("--dry-run", action="store_true", help="Run the checks and show the version update, without committing")
args = parser.parse_args()

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
new = parse_version(args.version)
tag = tag_name(new)

login = run(["gh", "api", "user", "--jq", ".login"])
upstream, fork = find_remotes(repo, login)
run(["git", "fetch", upstream, "main"], cwd=repo)

# The new version must be greater than the latest tag, and should not skip a number
current = latest_tag(repo, upstream)
print("Latest tag is %s, new tag is %s" % (tag_name(current), tag))
if new <= current:
    sys.exit("Version %s is not greater than the latest tag %s" % (version_string(new), tag_name(current)))
expected = [(current[0], current[1], current[2] + 1), (current[0], current[1] + 1, 0), (current[0] + 1, 0, 0)]
if new not in expected:
    print("Version %s skips a version number: the next versions after %s are %s"
          % (version_string(new), tag_name(current), ", ".join(version_string(v) for v in expected)))
    if ask("Continue with %s?" % version_string(new), ["y", "n"]) != "y":
        sys.exit("Aborting")

# Check whether the current checkout is at the HEAD of upstream main
head = run(["git", "rev-parse", "HEAD"], cwd=repo)
main = run(["git", "rev-parse", "%s/main" % upstream], cwd=repo)
use_local = False
if head != main:
    if subprocess.run(["git", "merge-base", "--is-ancestor", head, main], cwd=repo).returncode != 0:
        sys.exit("The current checkout (%s) has commits that are not in %s main: merge them first, "
                 "or check out %s/main" % (head[:9], UPSTREAM, upstream))
    print("The current checkout (%s) is not at the HEAD of %s main (%s):" % (head[:9], UPSTREAM, main[:9]))
    print(run(["git", "log", "--oneline", "%s..%s" % (head, main)], cwd=repo))
    answer = ask("Tag the (c)urrent checkout or %s (m)ain's HEAD?" % UPSTREAM, ["c", "m"])
    use_local = answer == "c"
base = head if use_local else main

# Make a worktree on a new branch from the chosen commit
branch = "UpdateVersion_" + tag
workdir = tempfile.mkdtemp(prefix="trig_tag_")
worktree = os.path.join(workdir, "worktree")
run(["git", "worktree", "add", "-b", branch, worktree, base], cwd=repo)
try:
    cmake_path = os.path.join(worktree, CMAKE)
    with open(cmake_path) as f:
        cmake = f.read()
    match = CMAKE_VERSION.search(cmake)
    if not match:
        sys.exit("No project VERSION found in %s" % CMAKE)
    old = tuple(int(x) for x in match.groups()[1:])
    if new <= old:
        sys.exit("Version %s is not greater than the %s version %s" % (version_string(new), CMAKE, version_string(old)))
    with open(cmake_path, "w") as f:
        f.write(CMAKE_VERSION.sub(lambda m: m.group(1) + version_string(new), cmake, count=1))
    print(run(["git", "diff"], cwd=worktree))
    if args.dry_run:
        print("Dry run: not committing")
        sys.exit(0)

    run(["git", "commit", "-am", "Update version to %s" % version_string(new)], cwd=worktree)
    commit = run(["git", "rev-parse", "HEAD"], cwd=worktree)
    run(["git", "push", fork, branch], cwd=worktree)
    pr_url = run(["gh", "pr", "create", "-R", UPSTREAM, "--base", "main", "--head", "%s:%s" % (login, branch),
                  "--title", "Update version to %s" % version_string(new),
                  "--body", "Update the version in `%s` to %s for tag %s." % (CMAKE, version_string(new), tag)])
    print("Opened " + pr_url)
    pr = pr_url.rstrip("/").split("/")[-1]

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

    # Tag the merge commit, or the version update commit if tagging the current checkout
    target = commit if use_local else run(["gh", "pr", "view", pr, "-R", UPSTREAM, "--json", "mergeCommit",
                                           "--jq", ".mergeCommit.oid"])
    run(["gh", "release", "create", tag, "-R", UPSTREAM, "--target", target, "--title", tag, "--generate-notes"])
    run(["git", "fetch", upstream, "main", "--tags"], cwd=repo)
    print("Tagged %s at %s" % (tag, target[:9]))
finally:
    run(["git", "worktree", "remove", "--force", worktree], cwd=repo, check=False)
    run(["git", "branch", "-D", branch], cwd=repo, check=False)
    shutil.rmtree(workdir, ignore_errors=True)
