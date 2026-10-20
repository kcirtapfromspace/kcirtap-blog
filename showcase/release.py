"""Exact, signed catalog publication. Proposals and prereleases never publish."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from .store import canonical, digest, now, outside_git, require, verify_owner
from .domain import candidate, gate

VERSION = re.compile(r"showcase/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-rc\.[1-9][0-9]*)?")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
EMPTY = {"schema": 1, "version": "0.0.0", "previous_catalog_hash": None, "stories": []}


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    require(p.returncode == 0, "Git release verification failed")
    return p.stdout


def tag_catalog(repo, tag, signers):
    require(VERSION.fullmatch(tag), "Wrong showcase tag namespace")
    require(git(repo, "cat-file", "-t", "refs/tags/" + tag).strip() == b"tag", "Annotated signed tag required")
    signers = outside_git(signers)
    git(repo, "-c", "gpg.format=ssh", "-c", f"gpg.ssh.allowedSignersFile={signers}", "verify-tag", tag)
    commit = git(repo, "rev-parse", tag + "^{commit}").decode().strip()
    body = git(repo, "cat-file", "tag", "refs/tags/" + tag).decode().split("\n\n", 1)[1]
    message = body.split("-----BEGIN SSH SIGNATURE-----", 1)[0].strip()
    approval = json.loads(message)
    raw = git(repo, "show", f"{commit}:showcase/catalog.json")
    catalog = json.loads(raw)
    require(approval == {"schema": 1, "kind": "stable" if "-rc." not in tag else "prerelease", "blog_commit": commit, "catalog_hash": digest(raw), "version": tag.removeprefix("showcase/v")}, "Signature does not bind exact commit, catalog and version")
    require(catalog["version"] == approval["version"], "Catalog version differs from release")
    for story in catalog["stories"]:
        require(SLUG.fullmatch(story["slug"]), "Unsafe story path")
        require(set(story) == {"slug", "files"}, "Public catalog may contain only slugs and public file hashes")
        require("index.md" in story["files"], "Story article missing")
        for filename, expected in story["files"].items():
            require(filename == "index.md" or re.fullmatch(r"figure-[a-z0-9-]+\.(png|jpg|jpeg)", filename), "Only explicit public article/figures can be exported")
            data = git(repo, "show", f"{commit}:showcase-publication/{story['slug']}/{filename}")
            require(digest(data) == expected, "Published file differs from reviewed hash")
    return catalog, commit


def stable_catalog(repo, signers):
    tags = git(repo, "tag", "--list", "showcase/v*").decode().splitlines()
    stable = [t for t in tags if VERSION.fullmatch(t) and "-rc." not in t]
    stable.sort(key=lambda t: tuple(map(int, VERSION.fullmatch(t).groups()[:3])))
    previous = EMPTY
    last_commit = None
    for tag in stable:
        catalog, commit = tag_catalog(repo, tag, signers)
        require(catalog["previous_catalog_hash"] == (None if previous == EMPTY else digest(previous)), "Stable catalog history must be continuous")
        old = {s["slug"]: s for s in previous["stories"]}
        new = {s["slug"]: s for s in catalog["stories"]}
        require(len(new) == len(catalog["stories"]) and all(new.get(k) == v for k, v in old.items()), "Existing published stories must be preserved byte for byte")
        previous, last_commit = catalog, commit
    return previous, last_commit


def sync_public(repo, output, signers=None):
    """Public builder needs only signed public Git objects, never private state."""
    repo, output = Path(repo).resolve(), Path(output).resolve()
    tags = git(repo, "tag", "--list", "showcase/v*").decode().splitlines()
    stable = [t for t in tags if VERSION.fullmatch(t) and "-rc." not in t]
    if not stable:
        catalog, commit = EMPTY, None
        # Proposed catalogs may land for review. They are ignored until a
        # person signs a stable tag, avoiding a commit/signature dependency loop.
        # The output stays empty, even if the working tree proposes stories.
    else:
        require(signers, "Owner release signer trust must be installed by the operator")
        catalog, commit = stable_catalog(repo, signers)
    # This generated directory is isolated from normal posts and the section index.
    output.mkdir(parents=True, exist_ok=True)
    for p in output.iterdir():
        if p.is_dir():
            shutil.rmtree(p)
        elif p.name != "_index.md":
            p.unlink()
    for story in catalog["stories"]:
        dest = output / story["slug"]
        dest.mkdir()
        for filename in story["files"]:
            (dest / filename).write_bytes(git(repo, "show", f"{commit}:showcase-publication/{story['slug']}/{filename}"))
    return {"catalog_hash": digest(catalog), "blog_commit": commit, "version": catalog["version"]}


def prepare(store, tasks, policy, repo, version, previous=EMPTY):
    require(VERSION.fullmatch("showcase/v" + version), "Use semantic version or -rc.N")
    require(tasks and len(set(tasks)) == len(tasks), "Explicit nonempty selected catalog required")
    stories = list(previous["stories"])
    root = Path(repo).resolve()
    for task in tasks:
        g = gate(store, task, policy)
        require(g["ready"], "Release blocked: " + json.dumps(g))
        c = candidate(store, task)
        slug = c["slug"]
        require(SLUG.fullmatch(slug) and slug not in {s['slug'] for s in stories}, "Unsafe or already published slug")
        files = {"index.md": c["article_hash"]}
        for e in c["evidence"]:
            require(re.fullmatch(r"figure-[a-z0-9-]+\.(png|jpg|jpeg)", e["figure"]), "Safe inline filename required")
            files[e["figure"]] = e["inline_hash"]
        dest = root / "showcase-publication" / slug
        dest.mkdir(parents=True, exist_ok=True)
        for filename, key in files.items():
            (dest / filename).write_bytes(store.get(key))
        stories.append({"slug": slug, "files": files})
    catalog = {"schema": 1, "version": version, "previous_catalog_hash": None if previous == EMPTY else digest(previous), "stories": stories}
    (root / "showcase" / "catalog.json").write_bytes(canonical(catalog))
    store.append("release-proposal", "RELEASE", {"catalog_hash": digest(catalog), "version": version, "tasks": tasks, "status": "unsigned; commit public payload, then bind exact commit", "at": now()})
    return catalog


def bind_proposal(store, repo, version):
    require(not git(repo, "status", "--porcelain").strip(), "Commit the reviewed public payload before binding a release")
    commit = git(repo, "rev-parse", "HEAD").decode().strip()
    raw = git(repo, "show", f"{commit}:showcase/catalog.json")
    catalog = json.loads(raw)
    proposal = store.latest("RELEASE", "release-proposal")
    require(proposal and catalog["version"] == version and proposal["catalog_hash"] == digest(catalog), "No exact prepared proposal")
    result = {"schema": 1, "kind": "prerelease" if "-rc." in version else "stable", "blog_commit": commit, "catalog_hash": digest(raw), "version": version}
    store.put(result)
    store.append("bound-release", "RELEASE", {**result, "tasks": proposal["tasks"], "at": now()})
    return result


def verify_live(store, repo, tag, signers, fetch):
    require("-rc." not in tag, "Prerelease cannot complete launch")
    catalog, commit = tag_catalog(repo, tag, signers)
    from urllib.parse import quote
    for story in catalog["stories"]:
        for filename, expected in story["files"].items():
            # Deployment marker is emitted into public output by CI; the release
            # commit/catalog must agree, and each inline image must match bytes.
            if filename != "index.md":
                require(digest(fetch(f"https://kcirtap.io/showcase/{quote(story['slug'])}/{filename}")) == expected, "Live inline figure differs")
        html = fetch(f"https://kcirtap.io/showcase/{quote(story['slug'])}/").decode()
        require(f'content="{commit}"' in html and f'content="{digest(catalog)}"' in html, "Live blog release identity not verified")
    store.append("verified-blog-release", "RELEASE", {"tag": tag, "blog_commit": commit, "catalog_hash": digest(catalog), "at": now()})
    return catalog


def unsigned_candidate(store, repo, version, tasks, policy):
    """A blocked review artifact, not a publishable catalog or release tag."""
    require(VERSION.fullmatch('showcase/v' + version) and '-rc.' in version, 'Use an explicit -rc.N version')
    require(not git(repo, 'status', '--porcelain').strip(), 'Commit the implementation before binding an unsigned release candidate')
    commit = git(repo, 'rev-parse', 'HEAD').decode().strip()
    selections = [{"task_id": t, "candidate_hash": store.latest(t, 'candidate')["candidate_hash"], "gates": gate(store, t, policy)} for t in tasks]
    result = {"kind": "unsigned-release-candidate", "version": version, "base_blog_commit": commit,
              "working_tree_diff_hash": digest(git(repo, 'diff', '--binary', 'HEAD')),
              "selected_candidates": selections, "selected_catalog_hash": digest(selections),
              "publication": "blocked; this is neither a signed prerelease nor a signed stable release", "at": now()}
    store.append('unsigned-candidate', 'RELEASE', result)
    (store.root / ('release-' + version + '.json')).write_bytes(canonical(result))
    return result


def complete_launch(store, repo, tag, signers, policy, fetch):
    binding = store.latest('RELEASE', 'bound-release')
    require(binding and binding['kind'] == 'stable', 'No reviewed exact stable release binding')
    catalog, commit = tag_catalog(repo, tag, signers)
    require(binding['blog_commit'] == commit and binding['catalog_hash'] == digest(canonical(catalog)) and binding['version'] == catalog['version'], 'Release differs from the exact private review binding')
    approval = store.latest('RELEASE', 'release-approval')
    require(approval and all(approval.get(k) == binding[k] for k in ('blog_commit','catalog_hash','version')), 'Pending signed owner release approval')
    for task in binding['tasks']:
        require(gate(store, task, policy)['ready'], 'A gate became stale after the release proposal')
    verify_live(store, repo, tag, signers, fetch)
    for task in binding['tasks']:
        store.append('launch-complete', task, {'blog_commit':commit,'catalog_hash':digest(catalog),'version':catalog['version'],'at':now()})
    return {'verified': True, 'blog_commit':commit, 'version':catalog['version']}
