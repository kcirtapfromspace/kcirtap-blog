"""Build a local-only article preview without copying any private reviews."""
import shutil
import subprocess
from pathlib import Path
from .domain import candidate
from .store import digest, require


def build(store, task, repo, zola):
    c = candidate(store, task)
    root = store.root / 'previews' / task
    if root.exists():
        shutil.rmtree(root)
    source = root / 'source'
    source.mkdir(parents=True)
    repo = Path(repo).resolve()
    for folder in ('content', 'templates', 'sass', 'static'):
        shutil.copytree(repo / folder, source / folder)
    shutil.copy2(repo / 'config.toml', source / 'config.toml')
    # Preview does not fetch the separate private resume repository.
    resume = source / 'content/resume.md'
    resume.write_text(resume.read_text().replace('template = "resume.html"', 'template = "page.html"'))
    sudoku = source / 'content/sudoku.md'
    sudoku.write_text(sudoku.read_text().replace('template = "sudoku.html"', 'template = "page.html"') + '\nThe interactive game is not bundled in this article preview. Use the public Sudoku page.\n')
    (source / 'showcase-release.json').write_text('{"blog_commit":"local-unsigned-preview","catalog_hash":"unpublished","version":"preview"}')
    dest = source / 'content/showcase' / c['slug']
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'index.md').write_bytes(store.get(c['article_hash']))
    for e in c['evidence']:
        require(Path(e['figure']).name == e['figure'], 'Unsafe preview figure')
        (dest / e['figure']).write_bytes(store.get(e['inline_hash']))
    base = source / 'templates/base.html'
    base.write_text(base.read_text().replace('<body>', '<body><p style="padding:1rem;background:#593900;color:white;text-align:center">LOCAL UNSIGNED PREVIEW · Owner and evidence review pending</p>'))
    output = root / 'public'
    result = subprocess.run([str(zola), '--root', str(source), 'build', '--base-url', 'http://127.0.0.1:8795', '--output-dir', str(output)], capture_output=True)
    require(result.returncode == 0, 'Preview build failed: ' + result.stderr.decode())
    return {'directory': str(output), 'url': f'http://127.0.0.1:8795/showcase/{c["slug"]}/', 'article_hash':c['article_hash'], 'kind':'local-unsigned-preview'}
