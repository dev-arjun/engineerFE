# Becoming an Engineer - blog

A tiny static blog for becominganengineer.in. No frameworks, no build tools to
install, no server. Just Python 3 turning Markdown posts into plain HTML pages,
hosted free on GitHub Pages.

## Folder structure

```
engineerFE/
  build.py          The build script. Reads Markdown, writes the site.
  style.css         The blog stylesheet (copied into docs/ on build).
  landing.html      Your custom homepage. Copied as-is to become index.html.
  about.md          Source for the About page.
  posts/            Your blog posts, one Markdown file per post.
    hello-world.md  Placeholder first post. Replace or delete it.
  docs/             The finished site. GitHub Pages serves this folder.
  README.md         This file.
```

You only ever edit the Markdown files, `landing.html`, `style.css`, and
`build.py` (rarely). The `docs/` folder is generated: `python3 build.py docs`
wipes it and rebuilds from scratch.

## Writing a new post

1. Create a file in `posts/`, e.g. `posts/my-first-week-with-playwright.md`.
   Lowercase letters, numbers, hyphens. The filename becomes the URL:
   `becominganengineer.in/posts/my-first-week-with-playwright.html`.
2. Start with front matter, then a blank line:

   ```markdown
   ---
   title: My first week with Playwright
   date: 2026-10-05
   tags: Playwright, Locators
   readtime: 5 min read
   description: One or two sentences shown on the cards and in the RSS feed.
   ---

   Your post starts here...
   ```

   `tags` is a comma-separated list (drives the homepage filters).
   `readtime` and `description` are optional.

3. Write Markdown (headings, bold/italic, code blocks, lists, quotes, links,
   images, `---` for a rule). The first fenced code block is also shown in
   the homepage card's read modal.
4. Rebuild with `python3 build.py docs`, commit, push.

Or use the **+ button** on the live homepage: it creates the `posts/*.md`
file straight in this repo via the GitHub API. It asks for a fine-grained
personal access token once per browser session (kept in sessionStorage,
never in the repo). Create it at GitHub → Settings → Developer settings →
Personal access tokens → Fine-grained: repository access = only this repo,
Contents = Read and write. Note: the button saves the file; the live site
updates after `docs/` is rebuilt and pushed (step 4 above).

## GitHub Pages setup

Repo Settings → Pages → Deploy from a branch → `main` → `/docs`.
Custom domain: `becominganengineer.in` (the `CNAME` file in `docs/` already
contains it). DNS at Hostinger: four A records for `@` pointing to
`185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`,
and one CNAME for `www` pointing to `dev-arjun.github.io`. Tick Enforce
HTTPS once the certificate is ready.

## Notes

- The RSS feed lives at `/feed.xml` and `posts.json` feeds the homepage
  cards; both regenerate on every build.
- Delete the placeholder by removing `posts/hello-world.md` and rebuilding.
- Keep post filenames URL friendly: lowercase, hyphens instead of spaces.
