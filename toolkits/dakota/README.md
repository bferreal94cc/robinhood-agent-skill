# Dakota General Toolkit

Version 1.0.0 contains 19 skills copied from the installed Dakota General Toolkit plugin. All 207 bundled files, including licenses, scripts, examples and references, are preserved. `manifest.json` records SHA-256 hashes of the source files.

## Repository installation

Copilot discovers the complete skills in `.github/skills/`. Codex discovers the same skills through relative directory symlinks in `.agents/skills/`. These paths become available when this commit is in the branch checked out by the agent. No package installation is required to read the skills. On Windows, enable Git symlink support or use the local installer below.

Use the relevant skill by name in a prompt, for example `dakota-engineering-memory` or `dakota-trading-research`. Repository `AGENTS.md` and application security boundaries still apply. Installing workflow instructions does not supply external connections, credentials, runtime dependencies, or permission to execute scripts.

## Local Codex and Copilot CLI

After cloning or pulling this repository on your computer, run from its root:

```bash
python3 toolkits/dakota/install.py
```

On Windows, `py toolkits/dakota/install.py` is an alternative. This copies the toolkit to `~/.agents/skills/` for Codex and `~/.copilot/skills/` for Copilot CLI. Existing folders are preserved: the installer stops before copying if a target skill already exists. Restart the applications and inspect their skill lists to confirm discovery. The installer does not install ChatGPT plugins.

## ChatGPT

The plugin is already available in the ChatGPT session used to prepare this installation. Select Dakota General Toolkit from your plugins when starting another conversation. This repository does not change ChatGPT account settings or verify other devices.

## Verification and limits

The installation is checked for exact source hashes, skill frontmatter, resolved Codex symlinks, and installer copying/conflict behavior in a temporary home. Bundled workflows and third-party scripts have not been executed as part of installation. Local computer installation and host discovery must be confirmed on that computer.

Official documentation:

- https://learn.chatgpt.com/docs/build-skills
- https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills
- https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
