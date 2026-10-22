"""Synchronize the tap with a fully uploaded, verified stable Peer release."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


API_URL = "https://api.github.com/repos/lantern24/peer/releases/latest"
ASSET_NAME = "Peer-macOS-arm64.app.zip"
VERSION_PATTERN = r"[0-9]+[.][0-9]+[.][0-9]+"


def _single_match(pattern: str, text: str, label: str) -> re.Match:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {label}; found {len(matches)}")
    return matches[0]


def synchronize(root: Path) -> dict[str, str]:
    response = subprocess.run(
        ["gh", "api", API_URL],
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        release = json.loads(response.stdout)
    except ValueError:
        # Prefer gh's diagnostic for authentication, connection, or CLI failures.
        response.check_returncode()
        raise
    if response.returncode and isinstance(release, dict) and release.get("status") == "404":
        print("Pending: upstream has no latest stable release (HTTP 404).")
        return {"status": "pending"}
    response.check_returncode()

    if not isinstance(release, dict):
        raise ValueError("Release metadata must be an object")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Latest release must explicitly be non-draft and non-prerelease")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(rf"v({VERSION_PATTERN})", tag):
        raise ValueError("Release tag must have the form vMAJOR.MINOR.PATCH")
    version = tag[1:]
    assets = release.get("assets")
    if not isinstance(assets, list) or any(
        not isinstance(asset, dict) or not isinstance(asset.get("name"), str)
        for asset in assets
    ):
        raise ValueError("Release assets must be a list of named asset objects")
    matching_assets = [asset for asset in assets if asset["name"] == ASSET_NAME]
    if not matching_assets:
        print(f"Pending: {tag} has no {ASSET_NAME} asset yet.")
        return {"status": "pending"}
    if len(matching_assets) != 1:
        raise ValueError(f"Expected exactly one {ASSET_NAME} asset")
    asset = matching_assets[0]
    state = asset.get("state")
    if not isinstance(state, str) or not state:
        raise ValueError("Asset metadata must include its upload state")
    if state != "uploaded":
        print(f"Pending: {tag} asset is not fully uploaded yet.")
        return {"status": "pending"}

    size = asset.get("size")
    if type(size) is not int or size <= 0:
        raise ValueError("Uploaded asset size must be a positive integer")
    download_url = (
        f"https://github.com/lantern24/peer/releases/download/{tag}/{ASSET_NAME}"
    )
    if asset.get("browser_download_url") != download_url:
        raise ValueError("Asset download URL does not match the expected release URL")
    expected_digest = asset.get("digest")
    if expected_digest is not None and (
        not isinstance(expected_digest, str)
        or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", expected_digest)
    ):
        raise ValueError("Asset digest must be sha256: followed by 64 hexadecimal characters")

    cask_path = root / "Casks/peer.rb"
    readme_path = root / "README.md"
    # Preserve all bytes outside the release fields, including line endings.
    cask_bytes = cask_path.read_bytes()
    readme_bytes = readme_path.read_bytes()
    cask = cask_bytes.decode("utf-8")
    readme = readme_bytes.decode("utf-8")
    cask_version = _single_match(
        r'^[ \t]*version[ \t]+"([^"\r\n]*)"[ \t]*(?=\r?$)',
        cask,
        "standalone cask version stanza",
    )
    cask_checksum = _single_match(
        r'^[ \t]*sha256[ \t]+"([^"\r\n]*)"[ \t]*(?=\r?$)',
        cask,
        "standalone cask sha256 stanza",
    )
    readme_release = _single_match(
        rf"^Current release: \[Peer v{VERSION_PATTERN}\]"
        rf"\(https://github[.]com/lantern24/peer/releases/tag/v{VERSION_PATTERN}\)"
        r"[.](?=\r?$)",
        readme,
        "README current-release line",
    )
    current_version = cask_version.group(1)
    if not re.fullmatch(VERSION_PATTERN, current_version):
        raise ValueError("Current cask version must have the form MAJOR.MINOR.PATCH")
    if tuple(map(int, version.split("."))) < tuple(map(int, current_version.split("."))):
        raise ValueError(f"Refusing to downgrade Peer from {current_version} to {version}")

    digest = hashlib.sha256()
    downloaded_size = 0
    with tempfile.TemporaryDirectory(prefix="peer-release-") as directory:
        archive_path = Path(directory) / ASSET_NAME
        subprocess.run(
            [
                "gh", "release", "download", tag,
                "--repo", "github.com/lantern24/peer",
                "--pattern", ASSET_NAME,
                "--output", str(archive_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        with archive_path.open("rb") as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                downloaded_size += len(chunk)
                digest.update(chunk)
    if downloaded_size != size:
        raise ValueError(f"Asset size mismatch: expected {size} bytes, received {downloaded_size}")
    checksum = digest.hexdigest()
    if expected_digest is not None and checksum != expected_digest[7:].lower():
        raise ValueError("Downloaded asset SHA-256 does not match the release digest")

    # Apply edits backwards so both spans refer to the original cask buffer.
    for match, value in sorted(
        ((cask_version, version), (cask_checksum, checksum)),
        key=lambda edit: edit[0].start(1),
        reverse=True,
    ):
        cask = cask[:match.start(1)] + value + cask[match.end(1):]
    release_url = f"https://github.com/lantern24/peer/releases/tag/{tag}"
    release_line = f"Current release: [Peer v{version}]({release_url})."
    readme = readme[:readme_release.start()] + release_line + readme[readme_release.end():]
    replacements = (
        (cask_path, cask_bytes, cask.encode("utf-8")),
        (readme_path, readme_bytes, readme.encode("utf-8")),
    )
    status = "current"
    # Both files and every release/download invariant are validated before writes.
    for path, before, after in replacements:
        if before != after:
            path.write_bytes(after)
            status = "updated"
    return {
        "status": status,
        "version": version,
        "sha256": checksum,
        "release_url": release_url,
    }


def main() -> int:
    try:
        result = synchronize(Path(__file__).resolve().parents[2])
        lines = "".join(f"{key}={value}\n" for key, value in result.items())
        print(lines, end="")
        output_path = os.environ.get("GITHUB_OUTPUT")
        if output_path:
            with open(output_path, "a", encoding="utf-8") as output:
                output.write(lines)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        detail = str(error)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            detail = error.stderr.strip()
        print(f"Peer release synchronization failed: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
