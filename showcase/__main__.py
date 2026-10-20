"""Run python3 -m showcase --help. All private state is outside Git."""
import argparse
import json
import os
from pathlib import Path
import sys
from .store import Store, GateError, canonical, digest, require
from . import domain, github, jev, release, calibration


def load(path):
    return json.loads(Path(path).read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default=os.environ.get("SHOWCASE_STATE", str(Path.home() / ".local/share/kcirtap-showcase")))
    parser.add_argument("--policy", default=str(Path(__file__).with_name("policy.json")))
    parser.add_argument("--signers", default=os.environ.get("SHOWCASE_OWNER_SIGNERS"))
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("contract", "candidate", "import-owner"):
        sub.add_parser(name).add_argument("file")
    sub.add_parser("put").add_argument("file")
    p = sub.add_parser("discover"); p.add_argument("--repos", nargs="+", required=True); p.add_argument("--days", type=int, default=30)
    p = sub.add_parser("source"); p.add_argument("repo"); p.add_argument("pr", type=int); p.add_argument("--context", nargs="*", default=[])
    p = sub.add_parser("source-commit"); p.add_argument("repo"); p.add_argument("commit"); p.add_argument("--checkout", required=True); p.add_argument("--task", default="UNASSIGNED"); p.add_argument("--context", nargs="*", default=[])
    p = sub.add_parser("land"); p.add_argument("task"); p.add_argument("--prs", nargs="*", default=[], help="owner/repo#number"); p.add_argument("--commits", nargs="*", default=[], help="owner/repo@sha for owner-approved legacy direct commits")
    p = sub.add_parser("review"); p.add_argument("task"); p.add_argument("stage", choices=domain.STAGES)
    p = sub.add_parser("status"); p.add_argument("task")
    sub.add_parser("obligations")
    p = sub.add_parser("preview"); p.add_argument("task"); p.add_argument("--repo", default="."); p.add_argument("--zola", default="zola")
    p = sub.add_parser("queue"); p.add_argument("--port", type=int, default=8766)
    p = sub.add_parser("export-obsidian"); p.add_argument("task"); p.add_argument("checkout")
    p = sub.add_parser("prepare"); p.add_argument("version"); p.add_argument("--tasks", nargs="+", required=True); p.add_argument("--repo", default=".")
    p = sub.add_parser("bind-release"); p.add_argument("version"); p.add_argument("--repo", default=".")
    p = sub.add_parser("candidate-release"); p.add_argument("version"); p.add_argument("--tasks", nargs="+", required=True); p.add_argument("--repo", default=".")
    p = sub.add_parser("verify-launch"); p.add_argument("tag"); p.add_argument("--repo", default=".")
    p = sub.add_parser("sync-public"); p.add_argument("--repo", default="."); p.add_argument("--output", default="content/showcase")
    args = parser.parse_args()
    policy = load(args.policy)
    # Public builds must not create/open any private database.
    if args.cmd == "sync-public":
        print(json.dumps(release.sync_public(args.repo, args.output, args.signers)))
        return
    store = Store(args.state)
    result = None
    if args.cmd == "contract":
        result = domain.contract(store, load(args.file))
    elif args.cmd == "put":
        result = {"sha256": store.put(Path(args.file).read_bytes())}
    elif args.cmd == "candidate":
        value = load(args.file); result = domain.add_candidate(store, value["task_id"], value)
    elif args.cmd == "import-owner":
        require(args.signers, "Install trusted owner signers outside Git")
        envelope = load(args.file)
        result = calibration.validate(store, policy, envelope, args.signers) if envelope["payload"]["kind"] == "calibration" else domain.owner_action(store, envelope, args.signers)
    elif args.cmd == "discover":
        result = {"new_snapshots": github.discover(store, args.repos, args.days)}
    elif args.cmd == "source":
        result = {"manifest_hash": store.put(github.collect_source(store, args.repo, args.pr, context_paths=args.context))}
    elif args.cmd == "source-commit":
        result = {"manifest_hash":store.put(github.collect_commit_source(store,args.repo,args.commit,args.checkout,args.task,args.context))}
    elif args.cmd == "land":
        prs = []
        approval = store.latest(args.task, "requirements-approval")
        for spec in args.prs:
            repo, number = spec.rsplit("#", 1)
            require(github.REPO.fullmatch(repo) and number.isdigit(), "Invalid PR reference")
            pr = github.api(f"repos/{repo}/pulls/{number}")
            tasks = github.TASK.findall(pr.get("body") or "")
            require(tasks == [args.task] or approval and spec in approval.get("legacy_prs", []), "PR lacks shared task identity; legacy mappings need a person's signature")
            prs.append({"repository": repo, "number": int(number), "task_id": args.task, "merged_at": pr.get("merged_at"), "merge_commit": pr.get("merge_commit_sha"), "api_hash": store.put(pr)})
        direct = []
        for spec in args.commits:
            repo, commit = spec.rsplit('@', 1)
            direct.append(github.legacy_commit(store, repo, commit, args.task))
        result = domain.land(store, args.task, {"contract_hash": store.latest(args.task, "contract")["contract_hash"], "prs": prs, "commits": direct})
    elif args.cmd == "review":
        result = jev.run_review(store, args.task, args.stage, policy)
    elif args.cmd == "status":
        result = domain.gate(store, args.task, policy)
    elif args.cmd == "obligations":
        result = domain.obligations(store, policy)
    elif args.cmd == "preview":
        from .preview import build
        result = build(store, args.task, args.repo, args.zola)
    elif args.cmd == "queue":
        from .server import make_server
        server = make_server(store, policy, os.environ.get("SHOWCASE_QUEUE_TOKEN", ""), args.port)
        print(f"Private owner desk: http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()
    elif args.cmd == "export-obsidian":
        from .store import outside_git
        c = domain.candidate(store, args.task)
        dest = Path(args.checkout).resolve() / "the_archives/showcase-drafts" / c["slug"]
        # Drafts are submitted OUTSIDE the archive folder consumed by the live workflow.
        dest.mkdir(parents=True, exist_ok=False)
        (dest / "index.md").write_bytes(store.get(c["article_hash"]))
        for e in c["evidence"]:
            require(release.SLUG.fullmatch(Path(e["figure"]).stem), "Unsafe figure")
            require(Path(e["figure"]).name == e["figure"], "Unsafe figure path")
            (dest / e["figure"]).write_bytes(store.get(e["inline_hash"]))
        result = {"draft": str(dest), "publication": "blocked; owner approval and signed stable release required"}
    elif args.cmd == "prepare":
        tags = release.git(args.repo, "tag", "--list", "showcase/v*").decode().splitlines()
        previous = release.stable_catalog(args.repo, args.signers)[0] if any('-rc.' not in t for t in tags) else release.EMPTY
        result = release.prepare(store, args.tasks, policy, args.repo, args.version, previous)
    elif args.cmd == "candidate-release":
        result = release.unsigned_candidate(store, args.repo, args.version, args.tasks, policy)
    elif args.cmd == "verify-launch":
        import urllib.request
        def fetch(url):
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        result = release.complete_launch(store, args.repo, args.tag, args.signers, policy, fetch)
    elif args.cmd == "bind-release":
        result = release.bind_proposal(store, args.repo, args.version)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (GateError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Showcase blocked: {exc}", file=sys.stderr)
        sys.exit(2)
