import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/update_peer.py"
SPEC = importlib.util.spec_from_file_location("update_peer", SCRIPT)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)

MACOS_ASSET_NAME = "Peer-macOS-arm64.app.zip"
LINUX_X86_64_ASSET_NAME = "Peer-Linux-x86_64.AppImage"
LINUX_ARM64_ASSET_NAME = "Peer-Linux-arm64.AppImage"
OLD_ASSET = b"original Peer macOS archive"
NEW_ASSET = b"replacement Peer macOS archive\n" * 50000
OLD_X86_64_ASSET = b"original Peer Linux AppImage"
NEW_X86_64_ASSET = b"replacement Peer Linux AppImage\n" * 40000
OLD_ARM64_ASSET = b"original Peer Linux arm64 AppImage"
NEW_ARM64_ASSET = b"replacement Peer Linux arm64 AppImage\n" * 30000
OLD_CHECKSUM = hashlib.sha256(OLD_ASSET).hexdigest()
NEW_CHECKSUM = hashlib.sha256(NEW_ASSET).hexdigest()
OLD_X86_64_CHECKSUM = hashlib.sha256(OLD_X86_64_ASSET).hexdigest()
NEW_X86_64_CHECKSUM = hashlib.sha256(NEW_X86_64_ASSET).hexdigest()
OLD_ARM64_CHECKSUM = hashlib.sha256(OLD_ARM64_ASSET).hexdigest()
NEW_ARM64_CHECKSUM = hashlib.sha256(NEW_ARM64_ASSET).hexdigest()
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
        "assets": [
            {
                "name": name,
                "state": "uploaded",
                "size": len(content),
                "browser_download_url": (
                    f"https://github.com/lantern24/peer/releases/download/v{version}/{name}"
                ),
                "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
            }
            for name, content in (
                (MACOS_ASSET_NAME, NEW_ASSET),
                (LINUX_X86_64_ASSET_NAME, NEW_X86_64_ASSET),
                (LINUX_ARM64_ASSET_NAME, NEW_ARM64_ASSET),
            )
        ],
    }


class SynchronizeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.cask = self.root / "Casks/peer.rb"
        self.cask.parent.mkdir()
        self.readme = self.root / "README.md"
        self.formula = self.root / "Formula/peer.rb"
        self.reset_files()

    def reset_files(self):
        self.cask.write_bytes(CASK.encode())
        self.readme.write_bytes(README.encode())
        if self.formula.exists():
            self.formula.unlink()
        if self.formula.parent.exists():
            self.formula.parent.rmdir()

    def existing_formula(self, version="0.2.0"):
        content = updater.render_linux_formula(version, OLD_X86_64_CHECKSUM, OLD_ARM64_CHECKSUM)
        self.formula.parent.mkdir(exist_ok=True)
        self.formula.write_bytes(content.encode())
        return content

    def files(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes() if path.is_file() else None
            for path in self.root.rglob("*")
        }

    def synchronize(
        self, release, asset=NEW_ASSET,
        x86_64_asset=NEW_X86_64_ASSET, arm64_asset=NEW_ARM64_ASSET,
    ):
        self.download_paths = []

        def run_gh(command, **kwargs):
            if command[1] == "api":
                if isinstance(release, Exception):
                    raise release
                if isinstance(release, subprocess.CompletedProcess):
                    return release
                return subprocess.CompletedProcess(command, 0, json.dumps(release), "")
            if command[1:3] == ["release", "download"]:
                target = Path(command[command.index("--output") + 1])
                name = command[command.index("--pattern") + 1]
                self.download_paths.append(target)
                content = {
                    MACOS_ASSET_NAME: asset,
                    LINUX_X86_64_ASSET_NAME: x86_64_asset,
                    LINUX_ARM64_ASSET_NAME: arm64_asset,
                }[name]
                if isinstance(content, Exception):
                    target.write_bytes(b"partial download")
                    raise content
                target.write_bytes(content)
                return subprocess.CompletedProcess(command, 0, "", "")
            raise AssertionError(f"Unexpected external command: {command}")

        try:
            with patch.object(updater.subprocess, "run", side_effect=run_gh):
                return updater.synchronize(self.root)
        finally:
            for path in self.download_paths:
                self.assertFalse(path.exists(), f"Downloaded asset was not cleaned up: {path}")

    def assert_ready_files(self, version):
        expected_cask = CASK.replace('version "0.2.0"', f'version "{version}"').replace(
            OLD_CHECKSUM, NEW_CHECKSUM
        )
        expected_readme = README.replace("v0.2.0", f"v{version}")
        self.assertEqual(self.cask.read_bytes(), expected_cask.encode())
        self.assertEqual(self.readme.read_bytes(), expected_readme.encode())
        formula = self.formula.read_text()
        self.assertEqual(
            re.findall(r'^[ \t]*version[ \t]+"([^"\r\n]+)"[ \t]*$', formula, re.MULTILINE),
            [version],
        )
        self.assertEqual(
            re.findall(r'^[ \t]*sha256[ \t]+"([^"\r\n]+)"[ \t]*$', formula, re.MULTILINE),
            [NEW_X86_64_CHECKSUM, NEW_ARM64_CHECKSUM],
        )

    def test_new_release_bootstraps_formula_and_is_idempotent(self):
        release = release_metadata()
        result = self.synchronize(release)
        self.assertEqual(result, {
            "status": "updated",
            "version": "0.3.0",
            "macos_sha256": NEW_CHECKSUM,
            "linux_x86_64_sha256": NEW_X86_64_CHECKSUM,
            "linux_arm64_sha256": NEW_ARM64_CHECKSUM,
            "release_url": "https://github.com/lantern24/peer/releases/tag/v0.3.0",
        })
        self.assert_ready_files("0.3.0")
        before = self.files()
        self.assertEqual(self.synchronize(release), dict(result, status="current"))
        self.assertEqual(self.files(), before)

    def test_same_version_replacement_updates_all_checksums(self):
        self.existing_formula()
        result = self.synchronize(release_metadata("0.2.0"))
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["macos_sha256"], NEW_CHECKSUM)
        self.assertEqual(result["linux_x86_64_sha256"], NEW_X86_64_CHECKSUM)
        self.assertEqual(result["linux_arm64_sha256"], NEW_ARM64_CHECKSUM)
        self.assert_ready_files("0.2.0")

    def test_version_comparison_is_numeric(self):
        self.existing_formula("0.9.0")
        result = self.synchronize(release_metadata("0.10.0"))
        self.assertEqual(result["status"], "updated")
        self.assert_ready_files("0.10.0")

    def test_pending_release_never_changes_files(self):
        valid = release_metadata()
        wrong_architecture = copy.deepcopy(valid)
        wrong_architecture["assets"][0]["name"] = "Peer-macOS-x64.app.zip"
        cases = {
            "no assets": dict(valid, assets=[]),
            "wrong architecture": wrong_architecture,
            "no release": subprocess.CompletedProcess(
                ["gh", "api"], 1,
                '{"message":"Not Found","status":"404"}', "gh: Not Found (HTTP 404)",
            ),
        }
        for index, asset in enumerate(valid["assets"]):
            cases[f"missing {asset['name']}"] = dict(
                valid, assets=[item for i, item in enumerate(valid["assets"]) if i != index]
            )
            uploading = copy.deepcopy(valid)
            uploading["assets"][index].update(state="new", size=0)
            cases[f"uploading {asset['name']}"] = uploading
        for existing_formula in (False, True):
            self.reset_files()
            if existing_formula:
                self.existing_formula()
            before = self.files()
            for name, release in cases.items():
                with self.subTest(name=name, existing_formula=existing_formula):
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
            "duplicate macOS": dict(valid, assets=valid["assets"] + [valid["assets"][0]]),
            "duplicate Linux x86_64": dict(valid, assets=valid["assets"] + [valid["assets"][1]]),
            "duplicate Linux arm64": dict(valid, assets=valid["assets"] + [valid["assets"][2]]),
            "duplicate Linux without macOS": dict(valid, assets=[valid["assets"][2]] * 2),
        }
        asset_cases = {
            "mismatched digest": {"digest": "sha256:" + "0" * 64},
            "malformed digest": {"digest": "sha256:not-a-hash"},
            "non-string digest": {"digest": 12},
            "wrong digest algorithm": {"digest": "sha512:" + NEW_CHECKSUM},
            "empty asset": {"size": 0},
            "negative size": {"size": -1},
            "non-integer size": {"size": str(len(NEW_ASSET))},
            "boolean size": {"size": True},
            "unexpected download URL": {"browser_download_url": "https://example.com/Peer.zip"},
            "missing upload state": {"state": None},
        }
        for index in (0, 1, 2):
            size = valid["assets"][index]["size"]
            asset_cases["truncated download"] = {"size": size + 1}
            asset_cases["oversized download"] = {"size": size - 1}
            for name, changes in asset_cases.items():
                release = copy.deepcopy(valid)
                release["assets"][index].update(changes)
                cases[f"{release['assets'][index]['name']}: {name}"] = release
        before = self.files()
        for name, release in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.synchronize(release)
                self.assertEqual(self.files(), before)

    def test_existing_formula_downgrade_fails_without_writes(self):
        self.existing_formula("0.10.0")
        before = self.files()
        with self.assertRaises(ValueError):
            self.synchronize(release_metadata("0.9.0"))
        self.assertEqual(self.files(), before)

    def test_corrupt_linux_download_never_partially_updates_packages(self):
        for existing_formula in (False, True):
            for argument, payload in (
                ("x86_64_asset", NEW_X86_64_ASSET),
                ("arm64_asset", NEW_ARM64_ASSET),
            ):
                for content in (b"corrupt Linux AppImage", b"x" * len(payload)):
                    with self.subTest(
                        existing_formula=existing_formula, asset=argument, size=len(content)
                    ):
                        self.reset_files()
                        if existing_formula:
                            self.existing_formula()
                        before = self.files()
                        with self.assertRaises(ValueError):
                            self.synchronize(release_metadata(), **{argument: content})
                        self.assertEqual(self.files(), before)

    def test_failed_linux_download_never_partially_updates_packages(self):
        for existing_formula in (False, True):
            for argument in ("x86_64_asset", "arm64_asset"):
                with self.subTest(existing_formula=existing_formula, asset=argument):
                    self.reset_files()
                    if existing_formula:
                        self.existing_formula()
                    before = self.files()
                    error = subprocess.CalledProcessError(1, ["gh"], stderr="download failed")
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.synchronize(release_metadata(), **{argument: error})
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
            for phase in ("discovery", "asset", "x86_64_asset", "arm64_asset"):
                with self.subTest(error=type(error).__name__, phase=phase):
                    with self.assertRaises(type(error)):
                        if phase == "discovery":
                            self.synchronize(error)
                        else:
                            self.synchronize(release_metadata(), **{phase: error})
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
        for mode in ("missing", "null", "uppercase"):
            with self.subTest(mode=mode):
                self.reset_files()
                release = release_metadata()
                for asset in release["assets"]:
                    if mode == "missing":
                        del asset["digest"]
                    elif mode == "null":
                        asset["digest"] = None
                    else:
                        asset["digest"] = asset["digest"].upper().replace("SHA256:", "sha256:")
                result = self.synchronize(release)
                self.assertEqual(result["macos_sha256"], NEW_CHECKSUM)
                self.assertEqual(result["linux_x86_64_sha256"], NEW_X86_64_CHECKSUM)
                self.assertEqual(result["linux_arm64_sha256"], NEW_ARM64_CHECKSUM)
                self.assert_ready_files("0.3.0")

    def test_malformed_anchors_prevent_changes(self):
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

    def test_malformed_formula_anchors_prevent_changes(self):
        formula = updater.render_linux_formula("0.2.0", OLD_X86_64_CHECKSUM, OLD_ARM64_CHECKSUM)
        cases = {
            "missing version": formula.replace('  version "0.2.0"\n', ""),
            "duplicate version": formula + '  version "0.2.0"\n',
            "invalid version": formula.replace('version "0.2.0"', 'version "latest"'),
            "multiline version": formula.replace('version "0.2.0"', 'version "0.2.\n0"'),
            "missing x86_64 checksum": formula.replace(f'    sha256 "{OLD_X86_64_CHECKSUM}"\n', ""),
            "missing arm64 checksum": formula.replace(f'    sha256 "{OLD_ARM64_CHECKSUM}"\n', ""),
            "duplicate architecture": formula.replace("on_arm do", "on_intel do"),
            "missing architecture": formula.replace("on_arm do", "on_macos do"),
            "duplicate checksum": formula + f'  sha256 "{OLD_X86_64_CHECKSUM}"\n',
            "multiline checksum": formula.replace(
                OLD_X86_64_CHECKSUM, OLD_X86_64_CHECKSUM[:32] + "\n" + OLD_X86_64_CHECKSUM[32:]
            ),
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                self.reset_files()
                self.formula.parent.mkdir()
                self.formula.write_bytes(content.encode())
                before = self.files()
                with self.assertRaises(ValueError):
                    self.synchronize(release_metadata())
                self.assertEqual(self.files(), before)

    def test_missing_file_prevents_changes_to_other_file(self):
        for missing in (self.cask, self.readme):
            with self.subTest(missing=missing.name):
                self.reset_files()
                missing.unlink()
                before = self.files()
                with self.assertRaises(FileNotFoundError):
                    self.synchronize(release_metadata())
                self.assertEqual(self.files(), before)
                self.assertFalse(missing.exists())

    def test_crlf_line_endings_are_preserved(self):
        self.cask.write_bytes(CASK.replace("\n", "\r\n").encode())
        self.readme.write_bytes(README.replace("\n", "\r\n").encode())
        formula = self.existing_formula()
        self.formula.write_bytes(formula.replace("\n", "\r\n").encode())
        self.synchronize(release_metadata())
        expected_cask = CASK.replace('version "0.2.0"', 'version "0.3.0"').replace(
            OLD_CHECKSUM, NEW_CHECKSUM
        ).replace("\n", "\r\n")
        expected_readme = README.replace("v0.2.0", "v0.3.0").replace("\n", "\r\n")
        expected_formula = formula.replace('version "0.2.0"', 'version "0.3.0"').replace(
            OLD_X86_64_CHECKSUM, NEW_X86_64_CHECKSUM
        ).replace(OLD_ARM64_CHECKSUM, NEW_ARM64_CHECKSUM).replace("\n", "\r\n")
        self.assertEqual(self.cask.read_bytes(), expected_cask.encode())
        self.assertEqual(self.readme.read_bytes(), expected_readme.encode())
        self.assertEqual(self.formula.read_bytes(), expected_formula.encode())

    def test_existing_formula_preserves_unrelated_content_and_spacing(self):
        formula = self.existing_formula()
        formula = formula.replace('  version "0.2.0"', '\tversion  "0.2.0"\t').replace(
            f'  sha256 "{OLD_X86_64_CHECKSUM}"', f' sha256\t"{OLD_X86_64_CHECKSUM}"  '
        )
        formula += '\n# Keep local packaging configuration unchanged.\n'
        self.formula.write_bytes(formula.encode())
        result = self.synchronize(release_metadata())
        self.assertEqual(result["status"], "updated")
        expected = formula.replace('"0.2.0"', '"0.3.0"').replace(
            OLD_X86_64_CHECKSUM, NEW_X86_64_CHECKSUM
        ).replace(OLD_ARM64_CHECKSUM, NEW_ARM64_CHECKSUM)
        self.assertEqual(self.formula.read_bytes(), expected.encode())
        self.assert_ready_files("0.3.0")

    def test_architecture_checksums_follow_blocks_not_order(self):
        formula = self.existing_formula()
        intel_block = re.search(r"  on_intel do\n.*?  end\n", formula, re.DOTALL).group()
        arm_block = re.search(r"  on_arm do\n.*?  end\n", formula, re.DOTALL).group()
        formula = formula.replace(intel_block, "").replace(arm_block, arm_block + "\n" + intel_block)
        self.formula.write_bytes(formula.encode())
        release = release_metadata()
        release["assets"].reverse()

        self.synchronize(release)

        expected = formula.replace('"0.2.0"', '"0.3.0"').replace(
            OLD_X86_64_CHECKSUM, NEW_X86_64_CHECKSUM
        ).replace(OLD_ARM64_CHECKSUM, NEW_ARM64_CHECKSUM)
        self.assertEqual(self.formula.read_bytes(), expected.encode())


if __name__ == "__main__":
    unittest.main()
