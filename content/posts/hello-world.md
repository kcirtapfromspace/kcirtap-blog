+++
title = "Hello, World!"
date = 2025-01-09
description = "The first post on the new blog, built with Zola."
[taxonomies]
tags = ["meta", "rust", "zola"]
+++

Welcome to the new blog! This site has been rebuilt from the ground up using [Zola](https://www.getzola.org/), a blazing-fast static site generator written in Rust.

## Why Zola?

After using Hugo for a while, I wanted something that:

1. **Stays fast** - Zola is incredibly quick at building sites
2. **Has simpler templating** - Tera templates feel more intuitive
3. **Is written in Rust** - Because why not?
4. **Works well with Obsidian** - My notes become blog posts seamlessly

## The New Publishing Workflow

The content for this blog now lives in my Obsidian vault. When I push changes to the vault repository, a GitHub Action automatically triggers a rebuild of this site. Here's how it works:

```
Obsidian Vault -> GitHub Push -> Blog Rebuild -> GitHub Pages
```

No more fighting with Hugo's markdown quirks. Just write in Obsidian, push, and publish.

## What's Next?

I'll be migrating some older content and writing new posts about:

- Infrastructure and DevOps
- Rust programming
- Developer tooling
- Random technical adventures

Stay tuned, and thanks for reading!

---

*This post was written in Obsidian and published automatically via GitHub Actions.*
