# Lantern24 Homebrew Tap

Homebrew casks for Lantern24 apps, including [Peer](https://github.com/lantern24/peer), a local repository viewer and code review workspace.

Current release: [Peer v0.2.0](https://github.com/lantern24/peer/releases/tag/v0.2.0).

## Install with Homebrew

Requirements: [Homebrew](https://brew.sh/), an Apple Silicon Mac (arm64), and macOS 13 or later. Intel Macs are not supported by the current release bundle. Node.js and Rust are only needed for development, not installation.

```sh
brew update
brew install --cask lantern24/tap/peer
```

The fully qualified cask name adds the [Lantern24 tap](https://github.com/lantern24/homebrew-tap) automatically; a separate `brew tap` command is not needed. Homebrew downloads the published release ZIP, verifies its SHA-256 checksum, installs `Peer.app` into `/Applications` by default, and installs Git as a runtime dependency.

### First launch on macOS

1. Open **Peer** from Applications or Spotlight.
2. If macOS blocks the launch because the developer cannot be verified, and you trust the download, open **System Settings → Privacy & Security** and scroll to **Security**.
3. Choose **Open Anyway** for Peer, if available, and confirm **Open** in the next dialog.

See [Apple's instructions for opening an app from an unidentified developer](https://support.apple.com/en-us/102445). Managed Macs may prohibit this exception. Do not disable Gatekeeper globally or bypass a malware warning.

### Upgrade

```sh
brew update
brew upgrade --cask lantern24/tap/peer
```

Quit Peer before upgrading, then reopen it afterward.

### Uninstall

```sh
brew uninstall --cask lantern24/tap/peer
```

This removes the app bundle; saved review data and preferences are retained.

## Release updates

The **Update Peer cask** GitHub Actions workflow checks the latest stable
`lantern24/peer` release at 00:17, 06:17, 12:17, and 18:17 UTC. It uses `gh api`
for release discovery and `gh release download` to fetch
`Peer-macOS-arm64.app.zip` into temporary storage. Python verifies its size and
any published SHA-256 digest, computes the checksum independently, and removes
the download afterward. Same-version asset replacements are checked too;
older versions are rejected.

Ready releases update the cask and the current-release link above through one
human-reviewed PR on `automation/update-peer`. The workflow never auto-merges.
Missing releases or unfinished uploads leave the tap and any existing update PR
unchanged until the next scheduled or manual check. Invalid metadata or failed
downloads fail the run visibly.

The workflow must be merged into the default branch before it can be scheduled
or manually dispatched:

```sh
gh workflow run update-peer.yml --repo lantern24/homebrew-tap --ref main
```

It uses the built-in `GITHUB_TOKEN`. If GitHub refuses PR creation, enable
**Settings → Actions → General → Workflow permissions → Allow GitHub Actions to
create and approve pull requests**. Tests and the Ruby syntax check run before
PR creation because token-created PRs do not trigger ordinary PR workflows.

[GitHub schedules are best-effort](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
and can be delayed or dropped. GitHub disables schedules in public repositories
after 60 days without activity; a maintainer must then re-enable the workflow
in Actions.

To verify or synchronize locally (Python 3, Ruby, and [GitHub CLI](https://cli.github.com/) required):

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 .github/scripts/update_peer.py
ruby -c Casks/peer.rb
```

The tests are offline and do not require `gh` or credentials. The updater requires
GitHub CLI authentication: run `gh auth login` locally or supply `GH_TOKEN`.
GitHub-hosted Ubuntu runners already provide `gh`; the workflow supplies the
built-in repository token. GitHub CLI handles HTTPS and authentication for
release discovery and downloads, so no Python CA-bundle configuration is needed.
