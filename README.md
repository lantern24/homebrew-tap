# Lantern24 Homebrew Tap

Homebrew casks for Lantern24 apps, including [Peer](https://github.com/lantern24/peer), a local repository viewer and code review workspace.

## Install with Homebrew

Requirements: [Homebrew](https://brew.sh/), an Apple Silicon Mac (arm64), and macOS 13 or later. Intel Macs are not supported by the current release bundle. Node.js and Rust are only needed for development, not installation.

```sh
brew update
brew install --cask lantern24/tap/peer
```

The fully qualified cask name adds the [Lantern24 tap](https://github.com/lantern24/homebrew-tap) automatically; a separate `brew tap` command is not needed. Homebrew downloads the published release ZIP, verifies its SHA-256 checksum, installs `Peer.app` into `/Applications` by default, and installs Git as a runtime dependency.

### First launch on macOS

Current releases are ad-hoc signed, not Developer ID signed or notarized by Apple. A valid signature protects bundle integrity but does not make Gatekeeper trust the app; Homebrew installation does not remove this distinction.

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

If you installed v0.1.0 and macOS reports the app as damaged, upgrade to v0.1.1 or later: v0.1.0 had an invalid bundle signature. The integrity fix does not add notarization. If a newer version still reports damage, [report the problem](https://github.com/lantern24/peer/issues) rather than treating it as an ordinary unidentified-developer warning.

### Uninstall

```sh
brew uninstall --cask lantern24/tap/peer
```

This removes the app bundle; saved review data and preferences are retained.
