import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/update_peer.py"
SPEC = importlib.util.spec_from_file_location("update_peer", SCRIPT)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)

OLD_ASSET = b"original Peer archive"
NEW_ASSET = b"replacement Peer archive\n" * 50000
OLD_CHECKSUM = hashlib.sha256(OLD_ASSET).hexdigest()
NEW_CHECKSUM = hashlib.sha256(NEW_ASSET).hexdigest()
CASK = f'''cask "peer" do
  version "0.2.0"
  sha256 "{OLD_CHECKSUM}"

  url "https://github.com/lantern24/peer/releases/download/v#{{version}}/Peer-macOS-arm64.app.zip"
  name "Peer"
  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura
  app "Peer.app"
end
'''
README = '''# Tap

Current release: [Peer v0.2.0](https://github.com/lantern24/peer/releases/tag/v0.2.0).

Install with `brew install --cask lantern24/tap/peer`.
Keep installation guidance unchanged.
'''


def release_metadata(version="0.3.0"):
    return {
        "draft": False,
        "prerelease": False,
        "tag_name": f"v{version}",
        "assets": [{
            "name": "Peer-macOS-arm64.app.zip",
            "state": "uploaded",
            "size": len(NEW_ASSET),
            "browser_download_url": (
                f"https://github.com/lantern24/peer/releases/download/v{version}/"
                "Peer-macOS-arm64.app.zip"
            ),
            "digest": f"sha256:{NEW_CHECKSUM}",
        }],
    }


class SynchronizeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.cask = self.root / "Casks/peer.rb"
        self.cask.parent.mkdir()
        self.readme = self.root / "README.md"
        self.reset_files()

    def reset_files(self):
        self.cask.write_bytes(CASK.encode())
        self.readme.write_bytes(README.encode())

    def files(self):
        return self.cask.read_bytes(), self.readme.read_bytes()

    def synchronize(self, release, asset=NEW_ASSET):
        def run_gh(command, **kwargs):
            if command[1] == "api":
                if isinstance(release, Exception):
                    raise release
                if isinstance(release, subprocess.CompletedProcess):
                    return release
                return subprocess.CompletedProcess(command, 0, json.dumps(release), "")
            if command[1:3] == ["release", "download"]:
                target = Path(command[command.index("--output") + 1])
                if isinstance(asset, Exception):
                    target.write_bytes(b"partial download")
                    raise asset
                target.write_bytes(asset)
                return subprocess.CompletedProcess(command, 0, "", "")
            raise AssertionError(f"Unexpected external command: {command}")

        with patch.object(updater.subprocess, "run", side_effect=run_gh):
            return updater.synchronize(self.root)

    def assert_ready_files(self, version):
        expected_cask = CASK.replace('version "0.2.0"', f'version "{version}"').replace(
            OLD_CHECKSUM, NEW_CHECKSUM
        )
        expected_readme = README.replace("v0.2.0", f"v{version}")
        self.assertEqual(self.files(), (expected_cask.encode(), expected_readme.encode()))

    def test_new_release_updates_both_files_and_is_idempotent(self):
        release = release_metadata()
        result = self.synchronize(release)
        self.assertEqual(result, {
            "status": "updated",
            "version": "0.3.0",
            "sha256": NEW_CHECKSUM,
            "release_url": "https://github.com/lantern24/peer/releases/tag/v0.3.0",
        })
        self.assert_ready_files("0.3.0")
        before = self.files()
        self.assertEqual(self.synchronize(release), dict(result, status="current"))
        self.assertEqual(self.files(), before)

    def test_same_version_replacement_updates_checksum(self):
        result = self.synchronize(release_metadata("0.2.0"))
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["sha256"], NEW_CHECKSUM)
        self.assert_ready_files("0.2.0")

    def test_version_comparison_is_numeric(self):
        result = self.synchronize(release_metadata("0.10.0"))
        self.assertEqual(result["status"], "updated")
        self.assert_ready_files("0.10.0")

    def test_pending_release_never_changes_files(self):
        absent = release_metadata()
        absent["assets"] = [{"name": "Peer-macOS-x64.app.zip"}]
        uploading = release_metadata()
        uploading["assets"][0].update(state="new", size=0)
        cases = {
            "no assets": dict(release_metadata(), assets=[]),
            "wrong architecture": absent,
            "uploading": uploading,
            "no release": subprocess.CompletedProcess(
                ["gh", "api"], 1,
                '{"message":"Not Found","status":"404"}', "gh: Not Found (HTTP 404)",
            ),
        }
        before = self.files()
        for name, release in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.synchronize(release), {"status": "pending"})
                self.assertEqual(self.files(), before)

    def test_invalid_release_or_asset_fails_before_writes(self):
        valid = release_metadata()
        cases = {
            "non-object release": [],
            "draft": dict(valid, draft=True),
            "prerelease": dict(valid, prerelease=True),
            "missing stability metadata": {key: value for key, value in valid.items() if key != "draft"},
            "lower version": release_metadata("0.1.9"),
            "malformed tag": dict(valid, tag_name="v0.3.0-rc.1"),
            "tag with output injection": dict(valid, tag_name="v0.3.0\nstatus=current"),
            "non-string tag": dict(valid, tag_name=3),
            "invalid assets": dict(valid, assets={}),
            "invalid asset object": dict(valid, assets=[None]),
            "missing asset name": dict(valid, assets=[{}]),
            "duplicate assets": dict(valid, assets=valid["assets"] * 2),
        }
        asset_cases = {
            "mismatched digest": {"digest": "sha256:" + "0" * 64},
            "malformed digest": {"digest": "sha256:not-a-hash"},
            "non-string digest": {"digest": 12},
            "wrong digest algorithm": {"digest": "sha512:" + NEW_CHECKSUM},
            "truncated download": {"size": len(NEW_ASSET) + 1},
            "oversized download": {"size": len(NEW_ASSET) - 1},
            "empty asset": {"size": 0},
            "negative size": {"size": -1},
            "non-integer size": {"size": str(len(NEW_ASSET))},
            "boolean size": {"size": True},
            "unexpected download URL": {"browser_download_url": "https://example.com/Peer.zip"},
            "missing upload state": {"state": None},
        }
        for name, changes in asset_cases.items():
            release = copy.deepcopy(valid)
            release["assets"][0].update(changes)
            cases[name] = release
        before = self.files()
        for name, release in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.synchronize(release)
                self.assertEqual(self.files(), before)

    def test_gh_failures_propagate_without_writes(self):
        before = self.files()
        for status in (403, 500):
            with self.subTest(status=status):
                response = subprocess.CompletedProcess(
                    ["gh", "api"], 1,
                    json.dumps({"status": str(status)}), f"gh: API failure (HTTP {status})",
                )
                with self.assertRaises(subprocess.CalledProcessError):
                    self.synchronize(response)
                self.assertEqual(self.files(), before)
        errors = (
            FileNotFoundError("gh is not installed"),
            subprocess.TimeoutExpired(["gh"], 60),
            subprocess.CalledProcessError(1, ["gh"], stderr="connection failed"),
        )
        for error in errors:
            for phase in ("discovery", "download"):
                with self.subTest(error=type(error).__name__, phase=phase):
                    with self.assertRaises(type(error)):
                        if phase == "discovery":
                            self.synchronize(error)
                        else:
                            self.synchronize(release_metadata(), error)
                    self.assertEqual(self.files(), before)

    def test_api_json_errors_preserve_gh_failure_diagnostics(self):
        before = self.files()
        for status, error_type in ((0, ValueError), (1, subprocess.CalledProcessError)):
            with self.subTest(exit_status=status):
                response = subprocess.CompletedProcess(
                    ["gh", "api"], status, "", "gh: authentication required",
                )
                with self.assertRaises(error_type):
                    self.synchronize(response)
                self.assertEqual(self.files(), before)

    def test_optional_or_uppercase_digest_uses_downloaded_bytes(self):
        for digest in ("missing", None, "sha256:" + NEW_CHECKSUM.upper()):
            with self.subTest(digest=digest):
                self.reset_files()
                release = release_metadata()
                if digest == "missing":
                    del release["assets"][0]["digest"]
                else:
                    release["assets"][0]["digest"] = digest
                result = self.synchronize(release)
                self.assertEqual(result["sha256"], NEW_CHECKSUM)
                self.assert_ready_files("0.3.0")

    def test_malformed_anchors_prevent_changes_to_either_file(self):
        cases = (
            (self.cask, CASK.replace('  version "0.2.0"\n', "")),
            (self.cask, CASK + '  version "0.2.0"\n'),
            (self.cask, CASK.replace('version "0.2.0"', 'version "latest"')),
            (self.cask, CASK.replace(f'  sha256 "{OLD_CHECKSUM}"\n', "")),
            (self.cask, CASK + f'  sha256 "{OLD_CHECKSUM}"\n'),
            (self.readme, README.replace("Current release:", "Latest release:")),
            (self.readme, README + README),
            (self.readme, README.replace("v0.2.0", "v0.2")),
        )
        for path, content in cases:
            with self.subTest(path=path.name, content=content):
                self.reset_files()
                path.write_bytes(content.encode())
                before = self.files()
                with self.assertRaises(ValueError):
                    self.synchronize(release_metadata())
                self.assertEqual(self.files(), before)

    def test_missing_file_prevents_changes_to_other_file(self):
        for missing, remaining in ((self.cask, self.readme), (self.readme, self.cask)):
            with self.subTest(missing=missing.name):
                self.reset_files()
                missing.unlink()
                before = remaining.read_bytes()
                with self.assertRaises(FileNotFoundError):
                    self.synchronize(release_metadata())
                self.assertEqual(remaining.read_bytes(), before)
                self.assertFalse(missing.exists())

    def test_crlf_line_endings_are_preserved(self):
        self.cask.write_bytes(CASK.replace("\n", "\r\n").encode())
        self.readme.write_bytes(README.replace("\n", "\r\n").encode())
        self.synchronize(release_metadata())
        expected_cask = CASK.replace('version "0.2.0"', 'version "0.3.0"').replace(
            OLD_CHECKSUM, NEW_CHECKSUM
        ).replace("\n", "\r\n")
        expected_readme = README.replace("v0.2.0", "v0.3.0").replace("\n", "\r\n")
        self.assertEqual(self.files(), (expected_cask.encode(), expected_readme.encode()))


if __name__ == "__main__":
    unittest.main()
