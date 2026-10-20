"""Read-only GitHub discovery and exact source capture; gh handles credentials."""
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from .store import digest, now, require

TASK = re.compile(r"(?m)^Task:\s*([A-Z][A-Z0-9-]{2,80})\s*$")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def api(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, check=False)
    require(result.returncode == 0, "GitHub read failed; inspect gh authentication privately")
    return json.loads(result.stdout)


def discover(store, repos, days=30, read=api):
    require(1 <= days <= 365, "Discovery window must be 1..365 days")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    count = 0
    for repo in repos:
        require(REPO.fullmatch(repo), "Invalid source repository")
        page = 1
        while True:
            pulls = read(f"repos/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=100&page={page}")
            recent = [p for p in pulls if p["updated_at"] >= since]
            for pr in recent:
                match = TASK.findall(pr.get("body") or "")
                task = match[0] if len(set(match)) == 1 else "UNASSIGNED"
                value = {"repository": repo, "number": pr["number"], "title": pr["title"], "task_id": task,
                         "state": pr["state"], "merged_at": pr.get("merged_at"), "merge_commit": pr.get("merge_commit_sha"),
                         "head_commit": pr["head"]["sha"], "updated_at": pr["updated_at"], "api_hash": store.put(pr)}
                previous = [e for e in store.events(kind="discovery") if (e["payload"]["repository"], e["payload"]["number"]) == (repo, pr["number"])]
                if not previous or digest(previous[-1]["payload"]) != digest(value):
                    store.append("discovery", task, value)
                    # Discovery never silently rejects, completes, or exempts work.
                    store.append("obligation", task, {"repository": repo, "number": pr["number"], "phase": "landed" if pr.get("merged_at") else "proposed", "at": now()})
                    count += 1
            if len(pulls) < 100 or len(recent) < len(pulls):
                break
            page += 1
    return count


def collect_source(store, repo, pr_number, read=api, context_paths=()):
    """Capture COMPLETE files at the immutable merge commit, never patches alone."""
    import base64
    require(REPO.fullmatch(repo) and int(pr_number) > 0, "Invalid PR")
    pr = read(f"repos/{repo}/pulls/{int(pr_number)}")
    require(pr.get("merged_at") and pr.get("merge_commit_sha"), "Source review requires landed work")
    commit = pr["merge_commit_sha"]
    changed, page = [], 1
    while True:
        files = read(f"repos/{repo}/pulls/{int(pr_number)}/files?per_page=100&page={page}")
        changed.extend(files)
        if len(files) < 100:
            break
        page += 1
    require(len(changed) == pr["changed_files"], "GitHub file list incomplete (including provider limits)")
    manifest = []
    for path in context_paths:
        if path not in {f["filename"] for f in changed}:
            changed.append({"filename": path, "status": "context"})
    for f in changed:
        # Deleted files are reviewed from the first parent, with surrounding code.
        ref = commit
        if f["status"] == "removed":
            parents = read(f"repos/{repo}/commits/{commit}")["parents"]
            require(parents, "Deleted source lacks a parent")
            ref = parents[0]["sha"]
        from urllib.parse import quote
        blob = read(f"repos/{repo}/contents/{quote(f['filename'], safe='/')}?ref={ref}")
        require(blob.get("encoding") == "base64" and blob.get("content"), "Source unavailable or too large; no truncated reviews")
        data = base64.b64decode(blob["content"])
        try:
            data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            encoding = "binary"
        manifest.append({"repository": repo, "pr": pr_number, "commit": commit, "read_ref": ref,
                         "path": f["filename"], "status": f["status"], "git_blob": blob["sha"],
                         "content_hash": store.put(data), "encoding": encoding, "role": "surrounding" if f["status"] == "context" else "changed"})
    store.append("source-capture", TASK.findall(pr.get("body") or "")[0] if TASK.findall(pr.get("body") or "") else "UNASSIGNED",
                 {"repository": repo, "pr": pr_number, "commit": commit, "manifest_hash": store.put(manifest), "api_hash": store.put(pr), "at": now()})
    return manifest


def legacy_commit(store, repo, commit, task, read=api):
    """Verify legacy direct commit ancestry; a signed owner maps its identity."""
    from .domain import sha
    require(REPO.fullmatch(repo) and sha(commit), 'Invalid legacy revision')
    approval = store.latest(task, 'requirements-approval')
    require(approval and repo + '@' + commit in approval.get('legacy_commits', []), 'Direct legacy mappings require the initial owner approval')
    branch = read('repos/' + repo)['default_branch']
    comparison = read(f'repos/{repo}/compare/{commit}...{branch}')
    require(comparison['status'] in ('ahead', 'identical') and comparison['merge_base_commit']['sha'] == commit, 'Legacy commit is not landed on the default branch')
    return {'task_id':task, 'repository':repo, 'commit':commit, 'api_hash':store.put(comparison)}


def collect_commit_source(store, repo, commit, checkout, task='UNASSIGNED', context_paths=(), read=api):
    """Exact legacy source, using Git trees to avoid API diff/file truncation."""
    from pathlib import Path
    from .domain import sha
    from .release import git
    require(REPO.fullmatch(repo) and sha(commit), 'Invalid source revision')
    remote = git(checkout, 'remote', 'get-url', 'origin').decode().strip().removesuffix('.git')
    require(remote in ('https://github.com/' + repo, 'git@github.com:' + repo), 'Checkout origin does not match the requested repository')
    metadata = read(f'repos/{repo}/commits/{commit}')
    require(metadata['sha'] == commit, 'GitHub revision identity differs')
    git(checkout, 'fetch', 'origin')
    require(git(checkout, 'rev-parse', commit + '^{commit}').decode().strip() == commit, 'Exact local revision unavailable')
    parents = metadata['parents']
    if parents:
        paths = git(checkout, 'diff', '--no-renames', '--name-only', '-z', parents[0]['sha'], commit).decode().split('\0')
    else:
        paths = git(checkout, 'ls-tree', '-r', '--name-only', '-z', commit).decode().split('\0')
    changed = {p for p in paths if p}
    manifest=[]
    for path in sorted(changed | set(context_paths)):
        require(not path.startswith('/') and '..' not in Path(path).parts, 'Unsafe source path')
        ref=commit
        exists=subprocess.run(['git','-C',str(checkout),'cat-file','-e',f'{ref}:{path}'],capture_output=True)
        status='changed'
        if exists.returncode:
            require(parents and path in changed, 'Missing surrounding source')
            ref=parents[0]['sha'];status='removed'
        data=git(checkout,'show',f'{ref}:{path}')
        try:
            data.decode();encoding='utf-8'
        except UnicodeDecodeError:
            encoding='binary'
        manifest.append({'repository':repo,'commit':commit,'read_ref':ref,'path':path,'status':status,'git_blob':git(checkout,'rev-parse',f'{ref}:{path}').decode().strip(),'content_hash':store.put(data),'encoding':encoding,'role':'changed' if path in changed else 'surrounding'})
    store.append('source-capture',task,{'repository':repo,'commit':commit,'manifest_hash':store.put(manifest),'api_hash':store.put(metadata),'at':now()})
    return manifest
