# kcirtap.io

Zola blog with the existing Obsidian → GitHub Actions → GHCR → Argo CD publishing path.

The internal feature showcase tooling is documented in
[docs/showcase/README.md](docs/showcase/README.md). Owner operations and local previews
are in [OPERATIONS.md](docs/showcase/OPERATIONS.md). The initial independent contract
is [contract.json](docs/showcase/contract.json).

Run the infrastructure checks with `python3 -m unittest discover -s tests -v`.
The public site never serves the private owner desk or review journal.
