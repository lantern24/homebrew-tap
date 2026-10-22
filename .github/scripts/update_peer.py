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
MACOS_ASSET_NAME = "Peer-macOS-arm64.app.zip"
LINUX_X86_64_ASSET_NAME = "Peer-Linux-x86_64.AppImage"
LINUX_ARM64_ASSET_NAME = "Peer-Linux-arm64.AppImage"
VERSION_PATTERN = r"[0-9]+[.][0-9]+[.][0-9]+"


def _single_match(pattern: str, text: str, label: str) -> re.Match:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {label}; found {len(matches)}")
    return matches[0]


def render_linux_formula(version: str, x86_64_checksum: str, arm64_checksum: str) -> str:
    return f'''class Peer < Formula
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"
  version "{version}"
  license "Apache-2.0"

  on_intel do
    url "https://github.com/lantern24/peer/releases/download/v#{{version}}/{LINUX_X86_64_ASSET_NAME}"
    sha256 "{x86_64_checksum}"
  end

  on_arm do
    url "https://github.com/lantern24/peer/releases/download/v#{{version}}/{LINUX_ARM64_ASSET_NAME}"
    sha256 "{arm64_checksum}"
  end

  depends_on :linux
  depends_on "git"

  def install
    appimage = File.basename(stable.url)
    chmod 0755, appimage
    system "./#{{appimage}}", "--appimage-extract"
    libexec.install Pathname("squashfs-root").children
    (bin/"peer").write_env_script libexec/"AppRun", {{}}
  end
end
'''


def _package_fields(
    text: str, label: str, version: str, architectures: tuple[str, ...] = ()
) -> tuple[re.Match, ...]:
    version_field = _single_match(
        r'^[ \t]*version[ \t]+"([^"\r\n]*)"[ \t]*(?=\r?$)',
        text,
        f"standalone {label} version stanza",
    )
    checksum_pattern = r'^[ \t]*sha256[ \t]+"([^"\r\n]*)"[ \t]*(?=\r?$)'
    if architectures:
        if len(re.findall(checksum_pattern, text, re.MULTILINE)) != len(architectures):
            raise ValueError(f"Expected one {label} sha256 stanza per architecture")
        checksum_fields = tuple(
            _single_match(
                rf"^[ \t]*on_{arch}[ \t]+do[ \t]*\r?\n"
                r"(?:(?![ \t]*end\b)[^\n]*\n)*?"
                + checksum_pattern,
                text,
                f"{label} on_{arch} sha256 stanza",
            )
            for arch in architectures
        )
    else:
        checksum_fields = (
            _single_match(checksum_pattern, text, f"standalone {label} sha256 stanza"),
        )
    current_version = version_field.group(1)
    if not re.fullmatch(VERSION_PATTERN, current_version):
        raise ValueError(f"Current {label} version must have the form MAJOR.MINOR.PATCH")
    if tuple(map(int, version.split("."))) < tuple(map(int, current_version.split("."))):
        raise ValueError(
            f"Refusing to downgrade Peer {label} from {current_version} to {version}"
        )
    return (version_field, *checksum_fields)


def _replace_package_fields(
    text: str, fields: tuple[re.Match, ...], *values: str
) -> str:
    # Apply edits backwards so every span refers to the original buffer.
    for match, value in sorted(
        zip(fields, values),
        key=lambda edit: edit[0].start(1),
        reverse=True,
    ):
        text = text[:match.start(1)] + value + text[match.end(1):]
    return text


def _download_checksum(asset: dict, tag: str) -> str:
    name = asset["name"]
    digest = hashlib.sha256()
    downloaded_size = 0
    with tempfile.TemporaryDirectory(prefix="peer-release-") as directory:
        archive_path = Path(directory) / name
        subprocess.run(
            [
                "gh", "release", "download", tag,
                "--repo", "github.com/lantern24/peer",
                "--pattern", name,
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
    size = asset["size"]
    if downloaded_size != size:
        raise ValueError(
            f"Asset size mismatch for {name}: expected {size} bytes, received {downloaded_size}"
        )
    checksum = digest.hexdigest()
    expected_digest = asset.get("digest")
    if expected_digest is not None and checksum != expected_digest[7:].lower():
        raise ValueError(f"Downloaded {name} SHA-256 does not match the release digest")
    return checksum


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
    required_assets = {}
    pending_assets = []
    for name in (MACOS_ASSET_NAME, LINUX_X86_64_ASSET_NAME, LINUX_ARM64_ASSET_NAME):
        matching_assets = [asset for asset in assets if asset["name"] == name]
        if len(matching_assets) > 1:
            raise ValueError(f"Expected exactly one {name} asset")
        if not matching_assets:
            pending_assets.append(name)
            continue
        asset = matching_assets[0]
        state = asset.get("state")
        if not isinstance(state, str) or not state:
            raise ValueError(f"Asset metadata for {name} must include its upload state")
        if state != "uploaded":
            pending_assets.append(name)
            continue
        size = asset.get("size")
        if type(size) is not int or size <= 0:
            raise ValueError("Uploaded asset size must be a positive integer")
        download_url = f"https://github.com/lantern24/peer/releases/download/{tag}/{name}"
        if asset.get("browser_download_url") != download_url:
            raise ValueError("Asset download URL does not match the expected release URL")
        expected_digest = asset.get("digest")
        if expected_digest is not None and (
            not isinstance(expected_digest, str)
            or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", expected_digest)
        ):
            raise ValueError(
                "Asset digest must be sha256: followed by 64 hexadecimal characters"
            )
        required_assets[name] = asset
    if pending_assets:
        print(
            f"Pending: {tag} is waiting for fully uploaded assets: "
            f"{', '.join(pending_assets)}."
        )
        return {"status": "pending"}

    cask_path = root / "Casks/peer.rb"
    formula_path = root / "Formula/peer.rb"
    readme_path = root / "README.md"
    # Preserve all bytes outside the release fields, including line endings.
    cask_bytes = cask_path.read_bytes()
    readme_bytes = readme_path.read_bytes()
    cask = cask_bytes.decode("utf-8")
    readme = readme_bytes.decode("utf-8")
    cask_fields = _package_fields(cask, "cask", version)
    try:
        formula_bytes = formula_path.read_bytes()
    except FileNotFoundError:
        formula_bytes = None
    if formula_bytes is not None:
        formula = formula_bytes.decode("utf-8")
        formula_fields = _package_fields(formula, "formula", version, ("intel", "arm"))
    readme_release = _single_match(
        rf"^Current release: \[Peer v{VERSION_PATTERN}\]"
        rf"\(https://github[.]com/lantern24/peer/releases/tag/v{VERSION_PATTERN}\)"
        r"[.](?=\r?$)",
        readme,
        "README current-release line",
    )
    checksums = {
        name: _download_checksum(asset, tag) for name, asset in required_assets.items()
    }
    cask = _replace_package_fields(cask, cask_fields, version, checksums[MACOS_ASSET_NAME])
    if formula_bytes is None:
        formula = render_linux_formula(
            version, checksums[LINUX_X86_64_ASSET_NAME], checksums[LINUX_ARM64_ASSET_NAME]
        )
    else:
        formula = _replace_package_fields(
            formula, formula_fields, version,
            checksums[LINUX_X86_64_ASSET_NAME], checksums[LINUX_ARM64_ASSET_NAME],
        )
    release_url = f"https://github.com/lantern24/peer/releases/tag/{tag}"
    release_line = f"Current release: [Peer v{version}]({release_url})."
    readme = readme[:readme_release.start()] + release_line + readme[readme_release.end():]
    replacements = (
        (cask_path, cask_bytes, cask.encode("utf-8")),
        (formula_path, formula_bytes, formula.encode("utf-8")),
        (readme_path, readme_bytes, readme.encode("utf-8")),
    )
    status = "current"
    # Validate all release metadata, files, and downloads before changing the tap.
    if formula_bytes is None:
        formula_path.parent.mkdir(exist_ok=True)
    for path, before, after in replacements:
        if before != after:
            path.write_bytes(after)
            status = "updated"
    return {
        "status": status,
        "version": version,
        "macos_sha256": checksums[MACOS_ASSET_NAME],
        "linux_x86_64_sha256": checksums[LINUX_X86_64_ASSET_NAME],
        "linux_arm64_sha256": checksums[LINUX_ARM64_ASSET_NAME],
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
