# Public Repo Checklist

Use this checklist right before changing the repository visibility from private to public.

## Already in Place

These items are already configured in the repository:

- `README.md`
- installation, configuration, provider, architecture, FAQ, troubleshooting, and release docs
- `CHANGELOG.md`
- `ROADMAP.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `SUPPORT.md`
- issue templates
- pull request template
- GitHub Actions CI
- release tag `v0.1.1`
- GitHub release for `v0.1.1`

The GitHub community profile is currently at `100%`.

## Current Repository Settings

Current state already applied:

- issues enabled
- discussions enabled
- wiki disabled
- projects disabled
- squash merge enabled
- merge commits disabled
- rebase merge disabled
- delete branch on merge enabled
- update branch enabled
- topics configured
- repository description updated

## Final Manual Check Before Going Public

Confirm again:

- no secrets are committed
- no private URLs or internal-only notes remain in docs
- the release notes look acceptable for public users
- the README reflects the current product direction
- the license text matches your intent

## Optional Improvements Before Public Launch

- add a repository homepage URL if you have a landing page
- upload a custom GitHub social preview image
- pin a discussion post for support or roadmap notes
- add branch protection rules if your GitHub plan supports them

## Switch Visibility To Public

When you are ready:

```bash
gh repo edit ibitato/TriadLLM --visibility public
```

## Recommended Post-Public Checks

After changing visibility:

1. open the repo in an incognito browser window
2. verify the README renders correctly
3. verify docs links work from GitHub web
4. verify issue templates appear when creating an issue
5. verify the CI badge resolves correctly
6. verify the release page is visible
7. verify the Topics and Discussions tabs look right
