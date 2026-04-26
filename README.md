# GitHub Collaborator Updater

Bulk update repository collaborators for a GitHub owner by removing one user and adding another across repositories that match a naming prefix (or an explicit list of repos).

This repository contains:

- `update_github_collaborators.py` - CLI script that performs the updates.
- `compose_collaborator_email.py` - CLI helper that creates a markdown email draft from the run log.
- `repos_updated.md` - example notification/message content after a successful run.

## What It Does

For each target repository, the script:

1. Checks repository access.
2. Removes the collaborator set by `--remove-user`.
3. Adds (or updates) the collaborator set by `--add-user` with the selected permission.

By default, it runs in **dry-run mode** and prints what it would do without changing anything.

## Requirements

- Python 3.10+ (tested with modern Python)
- A GitHub token set in one of:
  - `GH_TOKEN`, or
  - `GITHUB_TOKEN`

The token must have permission to manage collaborators on the target repositories.

### How To Create The Token (GitHub)

You can use either a **fine-grained personal access token** (recommended) or a **classic personal access token**.

#### Option A: Fine-grained personal access token (recommended)

1. In GitHub, open:
   - `Settings` -> `Developer settings` -> `Personal access tokens` -> `Fine-grained tokens`
2. Click **Generate new token**.
3. Set:
   - **Token name**: something clear, for example `collaborator-updater`.
   - **Expiration**: choose your preferred validity period.
  - **Resource owner**: owner that holds the target repos (for this project, `your-org`).
   - **Repository access**: select either:
     - **Only select repositories** (least privilege), or
     - **All repositories** under that owner.
4. Under **Repository permissions**, set:
   - **Administration** -> **Read and write**
     - This is required to add/remove collaborators.
5. Generate and copy the token value.

#### Option B: Classic personal access token

1. In GitHub, open:
   - `Settings` -> `Developer settings` -> `Personal access tokens` -> `Tokens (classic)`
2. Click **Generate new token (classic)**.
3. Set a note and expiration.
4. Enable scope:
   - `repo`
     - This is the key scope used for private repository collaborator management.
5. Generate and copy the token value.

#### Set token in PowerShell

For current shell session:

```powershell
$env:GH_TOKEN = "<paste_token_here>"
```

Optional (persist across new PowerShell sessions):

```powershell
setx GH_TOKEN "<paste_token_here>"
```

Then open a new terminal session before running the script.

## Quick Start

### 1) Set your token

PowerShell:

```powershell
$env:GH_TOKEN = "<paste_token_here>"
```

### 2) Dry run first (safe default)

```powershell
python .\update_github_collaborators.py
```

### 3) Apply changes

```powershell
python .\update_github_collaborators.py --apply
```

## Defaults

If you run without arguments, these defaults are used:

- `--owner your-org`
- `--prefix repo-prefix-`
- `--remove-user old-collaborator`
- `--add-user new-collaborator`
- `--permission push`
- `--limit 100`
- Dry run mode (unless `--apply` is provided)

## CLI Options

```text
--owner <name>           GitHub owner/org name
--prefix <prefix>        Repository name prefix when discovering repos
--repo <name>            Specific repository name (repeatable); skips prefix discovery
--remove-user <user>     Collaborator to remove
--add-user <user>        Collaborator to add
--permission <perm>      One of: pull | triage | push | maintain | admin
--limit <n>              Max repositories to fetch during discovery (default: 100)
--apply                  Execute write operations (without this, script is dry run)
```

## Examples

Dry run with a custom owner/prefix:

```powershell
python .\update_github_collaborators.py --owner your-org --prefix repo-prefix-
```

Apply changes to explicitly listed repositories only:

```powershell
python .\update_github_collaborators.py `
  --owner your-org `
  --repo repo-one `
  --repo repo-two `
  --remove-user old-collaborator `
  --add-user new-collaborator `
  --permission push `
  --apply
```

Grant read-only access (`pull`) while applying:

```powershell
python .\update_github_collaborators.py --permission pull --apply
```

## Compose Email Draft

After running `update_github_collaborators.py`, you can generate a ready-to-send markdown email from the JSON log file.

### Defaults

If you run without arguments, these defaults are used:

- `--log-file collaborator_update_log.json`
- `--recipient Team Name`
- `--sender [Your Name]`
- `--output email.md`

### CLI Options

```text
--log-file <path>        Path to JSON log created by update_github_collaborators.py
--recipient <name>       Recipient name used in greeting
--sender <name>          Sender name used in sign-off
--output <path>          Output markdown file (default: email.md)
```

### Examples

Use defaults:

```powershell
python .\compose_collaborator_email.py
```

Custom recipient/sender and output file:

```powershell
python .\compose_collaborator_email.py `
  --log-file collaborator_update_log.json `
  --recipient "Team Name" `
  --sender "Your Name" `
  --output repos_updated.md
```

### End-to-End Workflow

Dry run + compose preview email draft:

```powershell
python .\update_github_collaborators.py `
  --owner your-org `
  --prefix repo-prefix- `
  --remove-user old-collaborator `
  --add-user new-collaborator `
  --permission push

python .\compose_collaborator_email.py `
  --log-file collaborator_update_log.json `
  --recipient "Team Name" `
  --sender "Your Name" `
  --output email.md
```

Apply changes + compose final email draft:

```powershell
python .\update_github_collaborators.py `
  --owner your-org `
  --prefix repo-prefix- `
  --remove-user old-collaborator `
  --add-user new-collaborator `
  --permission push `
  --apply

python .\compose_collaborator_email.py `
  --log-file collaborator_update_log.json `
  --recipient "Team Name" `
  --sender "Your Name" `
  --output repos_updated.md
```

## Example Prompts Used For All Repos

Use these copy/paste prompts/commands for a full `your-org` + `repo-prefix-*` rollout.

Prompt/command to preview all target repositories (dry run):

```powershell
python .\update_github_collaborators.py `
  --owner your-org `
  --prefix repo-prefix- `
  --remove-user old-collaborator `
  --add-user new-collaborator `
  --permission push
```

Prompt/command to apply collaborator changes to all matching repositories:

```powershell
python .\update_github_collaborators.py `
  --owner your-org `
  --prefix repo-prefix- `
  --remove-user old-collaborator `
  --add-user new-collaborator `
  --permission push `
  --apply
```

Prompt/command to rerun for a known subset of repositories only:

```powershell
python .\update_github_collaborators.py `
  --owner your-org `
  --repo repo-one `
  --repo repo-two `
  --repo repo-three `
  --remove-user old-collaborator `
  --add-user new-collaborator `
  --permission push `
  --apply
```

## Output and Exit Codes

- Prints per-repository status, including API errors.
- Final summary format:
  - `Done. Successful: X. Failed: Y.`
- Exit code:
  - `0` when all repositories succeed
  - `1` when any repository fails (or none matched)

## Recommended Workflow

1. Run dry-run and confirm target repos look correct.
2. Run with `--apply`.
3. Share/update `repos_updated.md` (or your own notification template) with recipients.

## How To Draft The Collaborator Notification Email

Use `compose_collaborator_email.py` after running the updater script to generate a collaborator-facing email draft in markdown.

1. Run collaborator updates first so the log file exists:

```powershell
python .\update_github_collaborators.py --apply
```

2. Generate the email draft:

```powershell
python .\compose_collaborator_email.py `
  --log-file collaborator_update_log.json `
  --recipient "Team Name" `
  --sender "Your Name" `
  --output repos_updated.md
```

3. Open `repos_updated.md`, review the list of updated repositories, then paste/send it to collaborators as your notification email.

## Troubleshooting

- **`Set GH_TOKEN or GITHUB_TOKEN...`**
  - Export a valid token in your shell session.
- **Repository listing fails (`Could not list repositories...`)**
  - Verify owner name and token permissions.
- **Remove/add collaborator API errors**
  - Confirm token access for each repository and that usernames are correct.
