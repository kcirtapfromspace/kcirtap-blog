# Owner operations

Requires Python 3.9+, Git, `gh`, `ssh-keygen`, and Zola 0.19.2 for previews.
No Python packages are required. Run commands from the blog checkout.

## Private configuration

Use a private persistent directory such as `~/.local/share/kcirtap-showcase`.
The CLI defaults there. Store credentials in the process environment or a secret
manager. Never place credentials, journal data, model inputs, responses or owner
feedback in this checkout, GitHub public artifacts, action logs, or site assets.
`TYPESAFE_API_KEY` is read only by the local review process. Do not paste it in chat.

Install an SSH allowed-signers file outside Git. For owner action signatures:

```text
owner namespaces="kcirtap-showcase" ssh-ed25519 YOUR_OWNER_PUBLIC_KEY
```

Set `SHOWCASE_OWNER_SIGNERS` to its path. The owner holds the private key. Agents
prepare payloads; people approve and sign. The tool provides no signing endpoint.

For signed Git release tags, install a separate allowed-signers file with namespace
`git`. Set the blog repository's **operator-controlled** Actions variable
`SHOWCASE_RELEASE_SIGNERS` to that public key trust line. This is public key material,
not a model secret. Restrict who may change it. Configure a protected release
environment and require an owner review before enabling production automation.
No existing repository policy was changed automatically.

## Discovery and evidence

```sh
python3 -m showcase contract docs/showcase/contract.json
python3 -m showcase discover --repos OWNER/PROJECT OWNER/RELATED --days 30
python3 -m showcase obligations
python3 -m showcase source OWNER/PROJECT 123 --context path/to/caller.py path/to/README.md
```

The discovery command persists both proposed/open and landed work. Add the same
`Task: TASK-ID` line to every related PR. Do not infer relations from a similar
title alone. For legacy work, have the owner sign a `requirements-approval` payload
containing `contract_hash` and the exact `legacy_prs` list (`OWNER/REPO#123`).
Register the legacy initial contract first. Direct legacy commits need a signed `legacy_commits` list (`OWNER/REPO@SHA`) and `land --commits`; the tool verifies ancestry on the default branch. Source capture fails closed on API truncation. Binary assets retain their exact hashes; the signed deployment record must bind their runtime `artifact_hashes`, with original demonstrations. A text review never approves binary behavior.

A candidate JSON contains `task_id`, `slug`, `contract_hash`, `article_hash`,
`commits`, `source_manifest`, `workflow`, `limitations` and `evidence`.
Use `put FILE` to store the original bytes. For each requirement, an evidence entry
names `requirement_id`, actual landed `commits`, `outcome_hash`, `original_hash`,
`inline_hash`, exact Markdown heading `section`, relative `figure`, `classification`
(production, controlled-demonstration or research), and `limitations`.
An outcome records `observed`, `contradictions`, and `provenance` with recorder,
capture time, method, environment, real steps, exact runtime commits and execution
classification. Production needs independent deployment identity verification. A person signs
`feature-deployment` with `contract_hash`, exact `commits` and a
`verification_record_hash`. That original runtime record names `url`, `method`,
`observed` and `captured_at`. The outcome's `deployment_verification` names that
record hash. It cannot be replaced by a model's completion message.
Tests and receipts remain supporting provenance, never the observed result.

Capture real screenshots with browser tooling and retain original bytes. Inspect
both original and final inline pixels. Remove private repository views, credentials
and customer information before capture. If redaction is needed, preserve the
private original hash and record the transformation and final hash. A person signs
`visual-review` bound to the current `candidate_hash`, with the exact `{original_hash: inline_hash}` mapping,
`approved: true`, and `safe_for_public: true`. Writing review does not grant this.

```sh
python3 -m showcase candidate /PRIVATE/candidate.json
python3 -m showcase land TASK-ID --prs OWNER/PROJECT#123 OWNER/RELATED#456
python3 -m showcase review TASK-ID scope
python3 -m showcase review TASK-ID evidence
python3 -m showcase review TASK-ID writing
python3 -m showcase review TASK-ID ranking
python3 -m showcase status TASK-ID
```

The four report groups are feature evidence, incomplete review/transport, low
confidence, and pending owner actions. A failed gate is retained. Do not edit a
requirement, rerun a completed judgment, or lower a threshold to get a pass.

## Owner desk and signatures

Set a random `SHOWCASE_QUEUE_TOKEN` (32+ characters), then run:

```sh
python3 -m showcase queue
```

Open `http://127.0.0.1:8766/` and enter the local token. The server uses loopback,
Host and Origin checks, HttpOnly SameSite cookies, no-store responses and no access
logging. It has no public deployment or unauthenticated record API. Review the
article and original figures, select a choice, and save its exact canonical JSON
payload **without a trailing newline** as `/PRIVATE/choice.json`.

The owner runs:

```sh
ssh-keygen -Y sign -f /PRIVATE/OWNER_KEY -n kcirtap-showcase /PRIVATE/choice.json
```

Create the envelope without changing signed bytes:

```sh
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/PRIVATE/choice.json')
p.with_name('envelope.json').write_text(json.dumps({
    'payload': json.loads(p.read_bytes()),
    'signature': Path(str(p)+'.sig').read_text()
}))
PY
python3 -m showcase import-owner /PRIVATE/envelope.json
```

Every payload has `actor: owner`, `at`, `kind`, `task_id`, and `previous` (null
initially, or the hash of the preceding event of that kind). Choices bind the
current `candidate_hash`. Requirements bind `contract_hash`. Corrections add
history and require the previous action hash. Replays and stale choices are rejected.

Calibration is a signed `POLICY` action binding the exact `policy_hash`. Each
example names `stage`, `request_hash`, `response_hash`, `labels` keyed by question,
`split: held-out`, and `label_recorded_before_review: true`. Use representative
owner-labeled examples, including negative and borderline cases, kept separate
from policy development. Import validates original receipts, sample counts and
accuracy. The proposed floors remain unchanged. A signed statement is an owner
attestation of the held-out process; the program cannot infer independent labels.

## Obsidian and local preview

```sh
python3 -m showcase export-obsidian TASK-ID /PRIVATE/OBSIDIAN_CHECKOUT
python3 -m showcase preview TASK-ID --zola /PATH/TO/zola
```

The draft goes to `the_archives/showcase-drafts/SLUG`, outside the folder consumed
by the current production sync. Submit that folder through an ordinary Obsidian
PR. Do not copy it into `the_archives/archives`; showcase publication uses the
signed catalog allowlist. Private reviews and feedback never enter that PR.

The preview result reports its private output directory. Serve it on loopback:

```sh
python3 -m http.server 8795 --bind 127.0.0.1 --directory /PRIVATE/PREVIEW/public
```

The preview uses an explicit unsigned banner and omits the private resume data.
It is not deployment evidence. The ordinary site build still requires the existing
resume and WASM sync steps; no private content is fetched for a local preview.

## Release

Before gates pass, retain a private unsigned candidate with its exact blockers:

```sh
python3 -m showcase candidate-release 0.1.0-rc.1 --tasks TASK-ID
```

After proof, calibration and owner gates pass:

```sh
python3 -m showcase prepare 0.1.0-rc.1 --tasks TASK-ID
```

Review public `showcase-publication` files and the allowlist catalog. Commit them
through the repository's existing PR process. Then, from that clean exact commit:

```sh
python3 -m showcase bind-release 0.1.0-rc.1
```

The output is the exact canonical Git tag message. The person signs an annotated
`showcase/v0.1.0-rc.1` tag with their approved SSH key. A signed prerelease retains
reviewed content but the public sync ignores it. A stable release requires a new
catalog version, exact binding, signed `release-approval` action (`task_id: RELEASE`),
and a person-signed `showcase/vX.Y.Z` tag. The stable tag's JSON message contains
only `schema: 1`, `kind: stable`, `blog_commit`, raw-byte `catalog_hash`, and `version`.
Never sign or push a release on the owner's behalf.

The public builder verifies every stable signature and each explicit file hash.
Catalog history must preserve prior stories. It exports articles and inline
PNG/JPEG figures only; it cannot read journal objects or model inputs. The existing
GHCR/Argo CD deployment must finish. Verify the deployed page metadata and inline
bytes before marking the launch complete:

```sh
python3 -m showcase verify-launch showcase/vX.Y.Z
```

No local artifact, green test, unsigned proposal, or merely reachable URL completes
a launch. A signed owner `maintenance-exemption` requires a recorded reason and
original contract hash. It exempts editorial selection only.

Install `integrations/obsidian-discovery.yml` in the private repository on a
persistent private runner after pinning the reviewed tool commit and configuring
read-only source access. Do not run private jobs on public pull requests. Back up
private state; ephemeral Actions runners cannot preserve launch obligations.
