# Obsidian Notes Repository Setup

This directory contains the files needed to set up your Obsidian vault for automatic blog publishing.

## Directory Structure

```
your-obsidian-vault/
├── posts/           # Published posts (synced to blog)
│   └── my-post.md
├── drafts/          # Work in progress (not synced)
├── templates/
│   └── blog-post.md # Obsidian template for new posts
└── .github/
    └── workflows/
        └── trigger-blog.yml  # Triggers blog rebuild
```

## Setup Instructions

### 1. Create GitHub Repository

Create a new repository (e.g., `obsidian-notes`) to hold your publishable content.

### 2. Copy These Files

Copy the following to your new repository:
- `.github/workflows/trigger-blog.yml`
- `posts/` directory
- `templates/blog-post.md` (optional, for Obsidian)

### 3. Create Personal Access Token

1. Go to GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens
2. Create a new token with:
   - Repository access: Select your **blog repository**
   - Permissions: Contents (Read and write), Actions (Read and write)
3. Copy the token

### 4. Add Secrets

**In your notes repository:**
- Add secret `BLOG_REPO_TOKEN` with the personal access token

**In your blog repository:**
- Add secret `NOTES_REPO_TOKEN` with a token that has read access to your notes repo

### 5. Update Repository Names

In `trigger-blog.yml`, update the repository name:
```yaml
repository: kcirtapfromspace/kcirtap-blog  # Your blog repo
```

### 6. Install Obsidian Git Plugin (Optional)

For automatic syncing from Obsidian:
1. Install the [Obsidian Git](https://github.com/denolehov/obsidian-git) plugin
2. Configure it to auto-commit and push changes

## Writing Posts

### Using the Template

1. In Obsidian, create a new note using the `blog-post` template
2. Fill in the frontmatter:
   ```
   +++
   title = "My Post Title"
   date = 2025-01-09
   description = "A brief description"
   [taxonomies]
   tags = ["tag1", "tag2"]
   +++
   ```
3. Write your content in Markdown
4. Save to the `posts/` directory
5. Commit and push

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Post title |
| `date` | Yes | Publication date (YYYY-MM-DD) |
| `description` | No | Summary for listings and SEO |
| `tags` | No | Array of tags for categorization |
| `draft` | No | Set to `true` to hide from listings |

## Publishing Workflow

```
1. Write in Obsidian
2. Save to posts/ directory
3. Commit & push (manual or via Obsidian Git)
4. GitHub Action triggers blog rebuild
5. Blog updates automatically
```

## Troubleshooting

### Posts not appearing?

1. Check the frontmatter format (must use `+++` delimiters for TOML)
2. Ensure the file is in the `posts/` directory
3. Check GitHub Actions logs for errors
4. Verify the date is not in the future

### Workflow not triggering?

1. Verify the `BLOG_REPO_TOKEN` secret is set correctly
2. Check that the repository name in the workflow matches your blog repo
3. Ensure you're pushing to the `main` branch
