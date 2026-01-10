#!/usr/bin/env python3
"""
Convert Hugo-style YAML frontmatter to Zola-compatible format.

Hugo uses root-level tags/categories:
---
tags:
  - python
  - rust
categories:
  - programming
---

Zola expects them under taxonomies:
---
taxonomies:
  tags:
    - python
    - rust
  categories:
    - programming
---

This script converts the format in-place for all markdown files in a directory.
"""

import os
import re
import sys
from pathlib import Path


def convert_frontmatter(content: str) -> str:
    """Convert Hugo-style frontmatter to Zola-compatible format."""

    # Check if file starts with YAML frontmatter
    if not content.startswith('---'):
        return content

    # Find the end of frontmatter
    second_delimiter = content.find('---', 3)
    if second_delimiter == -1:
        return content

    frontmatter = content[3:second_delimiter]
    body = content[second_delimiter + 3:]

    # Check if already has taxonomies section
    if 'taxonomies:' in frontmatter:
        return content

    # Extract tags and categories from root level
    tags_match = re.search(r'^tags:\s*\n((?:\s+-\s+.+\n)*)', frontmatter, re.MULTILINE)
    tags_inline_match = re.search(r'^tags:\s*\[([^\]]*)\]', frontmatter, re.MULTILINE)
    categories_match = re.search(r'^categories:\s*\n((?:\s+-\s+.+\n)*)', frontmatter, re.MULTILINE)
    categories_inline_match = re.search(r'^categories:\s*\[([^\]]*)\]', frontmatter, re.MULTILINE)

    tags = None
    categories = None

    # Parse tags (list format)
    if tags_match:
        tag_lines = tags_match.group(1)
        tags = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', tag_lines)
        tags = [t.strip() for t in tags]
        # Remove original tags section
        frontmatter = frontmatter[:tags_match.start()] + frontmatter[tags_match.end():]

    # Parse tags (inline format like [tag1, tag2])
    elif tags_inline_match:
        tags_str = tags_inline_match.group(1)
        if tags_str.strip():
            tags = [t.strip().strip('"\'') for t in tags_str.split(',')]
            tags = [t for t in tags if t]
        # Remove original tags line
        frontmatter = frontmatter[:tags_inline_match.start()] + frontmatter[tags_inline_match.end():]

    # Parse categories (list format)
    if categories_match:
        cat_lines = categories_match.group(1)
        categories = re.findall(r'-\s+["\']?([^"\'\n]+)["\']?', cat_lines)
        categories = [c.strip() for c in categories]
        # Remove original categories section
        frontmatter = frontmatter[:categories_match.start()] + frontmatter[categories_match.end():]

    # Parse categories (inline format)
    elif categories_inline_match:
        cats_str = categories_inline_match.group(1)
        if cats_str.strip():
            categories = [c.strip().strip('"\'') for c in cats_str.split(',')]
            categories = [c for c in categories if c]
        # Remove original categories line
        frontmatter = frontmatter[:categories_inline_match.start()] + frontmatter[categories_inline_match.end():]

    # If we found tags or categories, add taxonomies section
    if tags or categories:
        # Clean up any extra blank lines
        frontmatter = re.sub(r'\n{3,}', '\n\n', frontmatter)

        # Build taxonomies section
        taxonomies = '\ntaxonomies:\n'
        if tags:
            taxonomies += '  tags:\n'
            for tag in tags:
                taxonomies += f'    - "{tag}"\n'
        if categories:
            taxonomies += '  categories:\n'
            for cat in categories:
                taxonomies += f'    - "{cat}"\n'

        # Add taxonomies before end of frontmatter
        frontmatter = frontmatter.rstrip() + taxonomies

    return '---' + frontmatter + '---' + body


def process_file(file_path: Path) -> bool:
    """Process a single markdown file. Returns True if modified."""
    try:
        content = file_path.read_text(encoding='utf-8')
        converted = convert_frontmatter(content)

        if converted != content:
            file_path.write_text(converted, encoding='utf-8')
            print(f"Converted: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: convert_frontmatter.py <directory>")
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    modified_count = 0

    # Process all .md files recursively
    for md_file in directory.rglob('*.md'):
        if process_file(md_file):
            modified_count += 1

    print(f"Converted {modified_count} files")


if __name__ == '__main__':
    main()
