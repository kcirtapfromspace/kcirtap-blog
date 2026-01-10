#!/usr/bin/env python3
"""Convert Hugo-style frontmatter to Zola format.

This script converts root-level tags/categories to Zola's taxonomies: format.
"""

import sys
import re
import os
from pathlib import Path


def convert_frontmatter(content: str) -> str:
    """Convert Hugo frontmatter to Zola format."""
    # Check if file has YAML frontmatter
    if not content.startswith('---'):
        return content

    # Split frontmatter from content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return content

    frontmatter = parts[1]
    body = parts[2]

    # Check if taxonomies already exists
    if 'taxonomies:' in frontmatter:
        return content

    # Extract tags and categories from root level
    tags_match = re.search(r'^tags:\s*\n((?:\s+-\s+.+\n?)+)', frontmatter, re.MULTILINE)
    categories_match = re.search(r'^categories:\s*\n((?:\s+-\s+.+\n?)+)', frontmatter, re.MULTILINE)

    tags = []
    categories = []

    if tags_match:
        tag_lines = tags_match.group(1)
        tags = list(set(re.findall(r'-\s+(.+)', tag_lines)))  # Use set to deduplicate
        # Remove original tags block
        frontmatter = re.sub(r'^tags:\s*\n(?:\s+-\s+.+\n?)+', '', frontmatter, flags=re.MULTILINE)

    if categories_match:
        cat_lines = categories_match.group(1)
        categories = list(set(re.findall(r'-\s+(.+)', cat_lines)))  # Use set to deduplicate
        # Remove original categories block
        frontmatter = re.sub(r'^categories:\s*\n(?:\s+-\s+.+\n?)+', '', frontmatter, flags=re.MULTILINE)

    # Build taxonomies section if we have tags or categories
    if tags or categories:
        taxonomies = '\ntaxonomies:\n'
        if tags:
            taxonomies += '  tags:\n'
            for tag in sorted(tags):
                taxonomies += f'    - {tag}\n'
        if categories:
            taxonomies += '  categories:\n'
            for cat in sorted(categories):
                taxonomies += f'    - {cat}\n'

        # Add taxonomies before the closing ---
        frontmatter = frontmatter.rstrip() + taxonomies

    # Reconstruct the file
    return '---' + frontmatter + '---' + body


def process_file(filepath: Path) -> None:
    """Process a single markdown file."""
    print(f"Processing: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = convert_frontmatter(content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  Converted: {filepath}")
    else:
        print(f"  No changes: {filepath}")


def main():
    if len(sys.argv) < 2:
        print("Usage: convert_frontmatter.py <directory>")
        sys.exit(1)

    directory = Path(sys.argv[1])

    if not directory.exists():
        print(f"Directory not found: {directory}")
        sys.exit(1)

    # Find all markdown files
    md_files = list(directory.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")

    for filepath in md_files:
        process_file(filepath)

    print("Frontmatter conversion complete")


if __name__ == "__main__":
    main()
