# Internal feature showcase pipeline

This is engineering and editorial infrastructure for the blog owner. The public
site has an **In practice** section. It has no review queue, model endpoint,
feedback API, or customer-facing review feature.

The task for this change is `SHOWCASE-2026-001`. Carry `Task: SHOWCASE-2026-001`
in every related PR body. Its initial independent contract is in `contract.json`.
CI prevents edits once that file lands. Private feature contracts are immutable
from registration; landing records freeze their exact hashes. Legacy contracts
need an owner signature before their first landing record.

## Repository inspection, 2026-10-20

The starting workspace was empty. Repository discovery identified:

- The active Zola site in `kcirtapfromspace/kcirtap-blog`.
- The Obsidian content source, with `the_archives/archives` consumed by the live job.
- The related Sudoku wrapper and core repositories, used for candidate discovery.
- `kcirtap.io` is a separate older site repository with a release-please workflow.
  Its release automation does not govern this Zola checkout.
- The nearby Nerudo blog is a different forge/repository. Its sequencer and seal
  rules were inspected; they do not authorize merging this GitHub repository.

No AGENTS.md, Jev integration, release tags, or signing policy existed in the active
blog checkout. GitHub returned no rulesets and main branch protection returned
404. Merges in history include verified GitHub signatures; some direct commits
are unsigned. This implementation does not merge, sign, or change branch rules.
The existing deployment bot still writes its generated image manifest on main.

The live flow is an Obsidian dispatch plus a scheduled content comparison, then
Zola 0.19.2, GHCR images, an image manifest commit, and Argo CD automatic sync.
Authentication uses GitHub Actions secrets for content reads, dispatch, package
writes and cache purges. No secret values were read. The review tool uses local
`gh` authentication for read-only GitHub access. It never accepts repository
credentials from a model or a browser.

## Design

`store.py` keeps content-addressed original bytes and an append-only hash-chained
SQLite journal. The private state root and signer trust files must be outside
**all** Git trees. It is a single-owner local trust boundary: OS access to the
state directory is privileged. Back up the database and objects together to
private, access-controlled storage. SQLite triggers and hashes detect accidental
changes; they are not a defense against an administrator rewriting the database.

`github.py` discovers recent open and merged PRs, groups exact `Task:` identities,
and records persistent obligations. Ambiguous or missing identities stay
unassigned. Legacy grouping needs an explicit signed owner mapping. Source
capture reads complete files at immutable merge commits, including deleted files
from a parent. Unavailable source blocks completeness. Binary assets retain their exact bytes and hashes; they need a separate signed runtime artifact binding and observed outcome. There is no
patch-only shortcut or silent truncation. Source is split into bounded overlapping
chunks; each chunk is judged in context, followed by a workflow composition
judgment. A supporting repair need not implement a whole feature.

`jev.py` uses the official `POST https://api.typesafe.ai/v1/systemone` contract.
It pins `jev-1.13.0`, the documented stable model at implementation time. It keeps
the exact response bytes, typed answers, probability distributions, confidence,
resolved model, usage, request identifiers when returned, request hashes and
input hashes. It does not invent an explanatory response field. Text-only review
cannot approve screenshot pixels. The official image interface is experimental;
it is deliberately not used for the production visual gate.

There are three independent judgments: source scope; evidence/explanation (with
separate outcome and writing requests); and prominence. Only prominence sees
signed owner ranking examples. Changed feedback makes ranking stale. It cannot
change a contract or invalidate a feature into existence. There is no model
weight training. Changes to review code, source, articles, media, policy, or
feedback invalidate the relevant reviews. Completed unfavorable or low-confidence
judgments are retained. Explicit 429/529 transport rejections retry with retained
attempts. A lost response or malformed 200 is blocked without automatic resampling;
there is no official API idempotency guarantee to justify a blind retry.

The proposed confidence floor is 0.85 for each stage. No prior threshold existed.
Publication remains blocked until at least 12 distinct owner-labeled held-out
examples per stage validate the exact policy/model, with at least 90% accuracy
among decisions above the floor. These are proposals, not claims of calibration.
Keep labels, representative borderline/negative examples, original Jev receipts,
and the owner's signed validation statement privately. Do not lower a threshold
merely to pass a story. An existing calibrated policy must remain unchanged until
a separately reviewed calibration proposal replaces it.

`server.py` provides an authenticated loopback desk. It separates proposed/open
work, landed work and verified deployed work. It shows original figures, the
article, separate gate categories, and immutable decision history. The buttons
prepare an exact choice for the owner to sign; they do not apply an unsigned choice.
Promote, lower, skip, reject and defer are explicit. Corrections reference the
previous signed choice. Unselected work remains pending. A lower prominence
choice can still select an accurate story. Choices never waive proof or reviews.

`release.py` stages a public allowlist only after the gates pass. A release binds
the exact blog commit, catalog bytes and version. An annotated owner-signed stable
`showcase/vX.Y.Z` tag is the only public catalog authority. An unsigned proposal or
signed `-rc.N` tag does not publish. Signed catalogs form a continuous history and
must preserve every previously published story byte for byte. The public build
reads only signed public content; it never opens the private journal. Human key
trust is installed by the operator, outside PR-editable files.

Meaningful engineering remains a launch obligation through landing, deployment,
original evidence, Jev judgments, owner selection, and a verified related blog
release. A signed maintenance explanation can exempt editorial work. It cannot
claim deployment or waive feature evidence. Urgent engineering delivery remains
independent of editorial selection.

## Current candidate

The first draft, **A Sudoku board with an undo key**, has four real screenshots:
number entry, undo, Easy selection and the board theme switch. It describes the
existing complete browser play loop. It does not turn the recent cache repair
into a new game. The article and originals are private, outside the public Git tree.
The draft has proposed legacy requirements. They are **not** owner approved.

The live page did not expose an exact deployed commit. A separate HTTP asset
identity check returned 403. The recorded production outcomes are real, but the
commit-to-runtime link remains missing. Complete source snapshots have been collected. Source judgment and all live Jev judgments
remain pending. No synthetic test receipt is used as feature proof.

See `OPERATIONS.md` for commands and `RELEASE-CANDIDATE.md` for precise blockers.

Official references checked: [System One API](https://docs.typesafe.ai/api/system-one),
[models](https://docs.typesafe.ai/models), [images](https://docs.typesafe.ai/images),
[OpenAPI schema](https://api.typesafe.ai/openapi.json).
