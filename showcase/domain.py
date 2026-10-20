"""Deterministic gates. Model judgments and editorial choices never waive proof."""
import json
import re
from .store import GateError, canonical, digest, now, require, verify_owner

STAGES = ("scope", "evidence", "writing", "ranking")
ACTIONS = ("promote", "lower", "skip", "reject", "defer")
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def contract(store, value):
    task = value["task_id"]
    require(re.fullmatch(r"[A-Z][A-Z0-9-]{2,80}", task), "Stable task identity required")
    for field in ("audience", "problem", "before", "after"):
        require(isinstance(value.get(field), str) and bool(value[field].strip()), f"Missing {field}")
    requirements = value.get("requirements", [])
    require(bool(requirements), "Requirements cannot be empty")
    require(len({r['id'] for r in requirements}) == len(requirements), "Duplicate requirement")
    for r in requirements:
        require(all(isinstance(r.get(k), str) and r[k].strip() for k in ("id", "behavior", "action", "expected")), "Requirement needs behavior, action and expected result")
    existing = store.latest(task, "contract")
    require(existing is None or existing["contract_hash"] == digest(value), "Initial requirements are immutable; add an obligation, never replace them")
    if existing:
        return existing
    result = {"contract_hash": store.put(value), "at": now(), "legacy": bool(value.get("legacy", False))}
    store.append("contract", task, result)
    return result


def owner_action(store, envelope, signers):
    p = verify_owner(envelope, signers)
    task = p["task_id"]
    kind = p["kind"]
    require(kind in ("requirements-approval", "choice", "visual-review", "calibration", "maintenance-exemption", "release-approval", "feature-deployment"), "Unknown signed action")
    require(not any(e["payload"].get("envelope_hash") == digest(envelope) for e in store.events()), "Signed action replay")
    previous = store.events(task, kind)
    require(p.get("previous") == (previous[-1]["hash"] if previous else None), "Correction must reference the previous immutable action")
    if kind in ("requirements-approval", "maintenance-exemption"):
        c = store.latest(task, "contract")
        require(c and p.get("contract_hash") == c["contract_hash"], "Action bound to different requirements")
        if kind == "maintenance-exemption":
            require(bool(p.get("reason", "").strip()), "Person must explain the maintenance exemption")
    if kind == "choice":
        require(p.get("action") in ACTIONS, "Explicit owner choice required")
        c = store.latest(task, "candidate")
        require(c and p.get("candidate_hash") == c["candidate_hash"], "Choice has stale candidate inputs")
    if kind == "visual-review":
        c = store.latest(task, "candidate")
        require(c and p.get("candidate_hash") == c["candidate_hash"], "Visual review has stale candidate context")
        require(bool(p.get("media")) and p.get("approved") is True and p.get("safe_for_public") is True, "Review original and inline pixels for accuracy and privacy")
        for original, inline in p["media"].items():
            store.get(original)
            store.get(inline)
    if kind == "feature-deployment":
        c = store.latest(task, "contract")
        require(c and p.get("contract_hash") == c["contract_hash"], "Deployment approval needs exact initial requirements")
        require(p.get("commits") and all(sha(v) for v in p["commits"]), "Verify exact feature commits")
        record = json.loads(store.get(p["verification_record_hash"]))
        require(all(record.get(k) for k in ("url", "method", "observed", "captured_at")), "Deployment verification needs an original runtime record")
        require(str(record['url']).startswith('https://'), "Production verification must name a real HTTPS deployment")
    if kind == "release-approval":
        require(sha(p.get("blog_commit")) and sha(p.get("catalog_hash")) and p.get("version"), "Release approval needs exact commit, catalog and version")
    store.append(kind, task, {**p, "envelope_hash": store.put(envelope)}, expected_previous=p.get("previous"))
    return p


def land(store, task, record):
    c = store.latest(task, "contract")
    require(c is not None, "Record the initial contract first")
    require(record.get("contract_hash") == c["contract_hash"], "Landed requirement hash mismatch")
    prs = record.get("prs", [])
    direct = record.get("commits", [])
    require(prs or direct, "No landed work")
    require(all(p.get("task_id") == task and p.get("merged_at") and sha(p.get("merge_commit")) for p in prs), "Every landed PR needs task identity, merge commit and merged time")
    require(all(p.get("task_id") == task and sha(p.get("commit")) and p.get("api_hash") for p in direct), "Every direct legacy commit needs verified ancestry and task mapping")
    approval = store.latest(task, "requirements-approval")
    require(not c["legacy"] or approval is not None, "Legacy initial requirements need a person's signature")
    store.append("landing", task, {**record, "at": now()})
    store.append("freeze", task, {"contract_hash": c["contract_hash"], "at": now()})


def add_candidate(store, task, value):
    c = store.latest(task, "contract")
    require(c and value.get("contract_hash") == c["contract_hash"], "Candidate must bind initial contract")
    # Article, outcomes, source snapshots, and media are addressed by original bytes.
    store.get(value["article_hash"])
    for e in value.get("evidence", []):
        for key in ("original_hash", "inline_hash", "outcome_hash"):
            store.get(e[key])
    source = value.get("source_manifest", [])
    for item in source:
        store.get(item["content_hash"])
    result = {"candidate_hash": store.put(value), "at": now()}
    store.append("candidate", task, result)
    return result


def candidate(store, task):
    c = store.latest(task, "candidate")
    require(c is not None, "No candidate")
    return json.loads(store.get(c["candidate_hash"]))


def review_input_hashes(store, task):
    c = candidate(store, task)
    # Explicit projections are also used by Jev. Feedback and article edits must
    # never contaminate the independent source judgment.
    feedback = [e["hash"] for e in store.events(kind="choice")]
    from pathlib import Path
    reviewer = digest((Path(__file__).with_name("jev.py")).read_bytes())
    projections = {
        "scope": digest({"commits": c.get("commits"), "source_manifest": c.get("source_manifest"), "workflow": c.get("workflow")}),
        "evidence": digest({"contract_hash": c["contract_hash"], "commits": c.get("commits"), "evidence": c.get("evidence"), "article_hash": c["article_hash"]}),
        "writing": digest({"article_hash": c["article_hash"], "limitations": c.get("limitations")}),
        "ranking": digest({"scope": c.get("source_manifest"), "workflow": c.get("workflow"), "scope_reviews": [e["hash"] for e in store.events(task, "review") if e["payload"].get("stage") == "scope"], "feedback": feedback}),
    }
    return {k: digest({"projection": v, "reviewer": reviewer}) for k, v in projections.items()}


def evidence_errors(store, task):
    c = candidate(store, task)
    errors = []
    initial = json.loads(store.get(c["contract_hash"]))
    article = store.get(c["article_hash"]).decode()
    landed = store.latest(task, "landing")
    commits = set(c.get("commits", []))
    actual = ({p["merge_commit"] for p in landed.get("prs", [])} | {p["commit"] for p in landed.get("commits", [])}) if landed else set()
    if not landed or not commits or not commits.issubset(actual):
        errors.append("No verified landing for the candidate commits")
    visuals = store.latest(task, "visual-review")
    for req in initial["requirements"]:
        bindings = [e for e in c.get("evidence", []) if e.get("requirement_id") == req["id"]]
        if not bindings:
            errors.append(f"{req['id']}: missing feature demonstration")
        for e in bindings:
            if not e.get("commits") or not set(e["commits"]).issubset(commits):
                errors.append(f"{req['id']}: evidence commits do not match landing")
            if e.get("classification") not in ("production", "controlled-demonstration", "research"):
                errors.append(f"{req['id']}: execution classification missing")
            section = e.get("section", "")
            inline = e.get("figure", "")
            section_text = article.split(f"## {section}\n", 1)[-1].split("\n## ", 1)[0] if f"## {section}\n" in article else ""
            if not inline or not re.search(r'!\[[^\]]+\]\(' + re.escape(inline) + r'\)', section_text):
                errors.append(f"{req['id']}: inline figure missing from its article section")
            if not e.get("limitations"):
                errors.append(f"{req['id']}: honest limitations required")
            try:
                original = store.get(e["original_hash"])
                inline_bytes = store.get(e["inline_hash"])
                outcome = json.loads(store.get(e["outcome_hash"]))
                if not original.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')) or not inline_bytes.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff')):
                    errors.append(f"{req['id']}: original and inline figure must be real PNG/JPEG pixels")
                prov = outcome.get("provenance", {})
                if not outcome.get("observed") or outcome.get("contradictions"):
                    errors.append(f"{req['id']}: missing or contradictory observed outcome")
                if not all(prov.get(k) for k in ("recorder", "captured_at", "method", "environment", "steps")):
                    errors.append(f"{req['id']}: execution provenance incomplete")
                if not set(e["commits"]).issubset(set(prov.get("commits", []))):
                    errors.append(f"{req['id']}: observation lacks exact runtime commit binding")
                if prov.get("classification") != e.get("classification"):
                    errors.append(f"{req['id']}: inconsistent execution classification")
                deployment = store.latest(task, "feature-deployment")
                if e.get("classification") == "production" and (not deployment or prov.get("deployment_verification") != deployment.get("verification_record_hash")):
                    errors.append(f"{req['id']}: production deployment identity not verified")
                if not visuals or visuals.get("candidate_hash") != store.latest(task, "candidate")["candidate_hash"] or visuals.get("media", {}).get(e["original_hash"]) != e["inline_hash"]:
                    errors.append(f"{req['id']}: pending signed pixel and privacy review")
            except (KeyError, ValueError, OSError) as exc:
                errors.append(f"{req['id']}: original object unavailable: {exc.__class__.__name__}")
    return errors


def gate(store, task, policy):
    result = {"feature_evidence": [], "incomplete_review": [], "low_confidence": [], "pending_owner": [], "writing_quality": []}
    try:
        c = candidate(store, task)
        for error in evidence_errors(store, task):
            result["pending_owner" if "pending signed pixel" in error else "feature_evidence"].append(error)
        for error in source_errors(store, c):
            result["feature_evidence" if error.startswith("Binary artifact") else "incomplete_review"].append(error)
    except (GateError, KeyError, OSError) as exc:
        result["feature_evidence"].append(str(exc))
        return {**result, "ready": False}
    hashes = review_input_hashes(store, task)
    for stage in STAGES:
        records = [e["payload"] for e in store.events(task, "review") if e["payload"].get("stage") == stage and e["payload"].get("input_hash") == hashes[stage]]
        r = records[-1] if records else None
        if not r or r.get("status") != "complete" or r.get("policy_hash") != digest(policy):
            result["incomplete_review"].append(f"{stage}: missing, stale, failed transport or incomplete review")
            continue
        if r.get("model") != policy["model"]:
            result["incomplete_review"].append(f"{stage}: model identity differs from validated policy")
        for question, answer in r.get("answers", {}).items():
            if answer.get("confidence", 0) < policy["thresholds"][stage]:
                result["low_confidence"].append(f"{stage}/{question}: below unchanged confidence floor")
            decision = answer.get("choice")
            if stage == "writing" and decision in ("misleading", "unclear", "uncertain"):
                result["writing_quality"].append(f"{question}: {decision}; retain the separate writing review")
            elif decision in ("missing", "contradictory", "inaccurate"):
                result["feature_evidence"].append(f"{stage}/{question}: {decision}; retain original review")
            elif decision == "uncertain" and (stage == "evidence" or question == "workflow_scope"):
                result["incomplete_review"].append(f"{stage}/{question}: completed uncertain judgment needs clarified inputs, not invented requirements")
    calibration = store.latest("POLICY", "calibration")
    if not calibration or calibration.get("policy_hash") != digest(policy):
        result["pending_owner"].append("Validate this exact model and proposed thresholds on owner-labeled examples")
    deployment = store.latest(task, "feature-deployment")
    if not deployment or deployment.get("contract_hash") != c["contract_hash"] or not set(c.get("commits", [])).issubset(set(deployment.get("commits", []))):
        result["pending_owner"].append("Verify the feature deployment and sign its exact commit record")
    co = store.latest(task, "contract")
    if co["legacy"] and not store.latest(task, "requirements-approval"):
        result["pending_owner"].append("Approve the initial legacy requirements")
    decision = store.latest(task, "choice")
    current = store.latest(task, "candidate")["candidate_hash"]
    if not decision or decision.get("candidate_hash") != current:
        result["pending_owner"].append("Choose promote, lower, skip, reject or defer for the exact candidate")
    elif decision["action"] not in ("promote", "lower"):
        result["pending_owner"].append(f"Owner choice is {decision['action']}")
    result["ready"] = not any(result.values())
    return result


def obligations(store, policy):
    """No local file, green check, unverified URL or unsigned proposal is done."""
    result = []
    discoveries = {}
    for event in store.events(kind="discovery"):
        d = event["payload"]
        discoveries[(d["repository"], d["number"])] = d
    for d in discoveries.values():
        task = d["task_id"]
        exemption = store.latest(task, "maintenance-exemption")
        verified = [e for e in store.events(kind="launch-complete") if e["task"] == task]
        result.append({"task_id": task, "pr": d["number"], "repository": d["repository"],
                       "engineering": "landed; deployment still requires verification" if d["merged_at"] else "proposed/open",
                       "editorial": "verified blog release" if verified else "person-recorded maintenance exemption" if exemption else "open launch obligation",
                       "exemption_reason": exemption.get("reason") if exemption else None,
                       "gates": gate(store, task, policy) if store.latest(task, "candidate") else "Candidate and task contract required"})
    return result


def source_errors(store, c):
    errors = []
    captures = {}
    for event in store.events(kind="source-capture"):
        record = event["payload"]
        captures[(record.get("repository"), record["commit"])] = record
    expected = []
    for capture in captures.values():
        if capture["commit"] in c.get("commits", []):
            expected.extend(json.loads(store.get(capture["manifest_hash"])))
    actual = c.get("source_manifest", [])
    if not expected or digest(sorted(expected, key=canonical)) != digest(sorted(actual, key=canonical)):
        errors.append("Complete changed source and surrounding context are missing or stale against verified source captures")
    if not set(c.get("commits", [])).issubset({e['commit'] for e in expected}):
        errors.append("Not every landed commit has a complete source capture")
    binary = {e['content_hash'] for e in actual if e.get('encoding') == 'binary'}
    if binary:
        deployment = store.latest(c['task_id'], 'feature-deployment')
        record = json.loads(store.get(deployment['verification_record_hash'])) if deployment else {}
        if not binary.issubset(set(record.get('artifact_hashes', []))):
            errors.append('Binary artifact hashes lack an independent signed runtime binding; a text source review cannot approve binary behavior')
    return errors
