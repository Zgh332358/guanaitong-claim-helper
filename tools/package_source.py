"""Package reviewed public files only; never walk private runtime directories."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import zipfile

ROOT_FILES = (
    ".gitignore", "README.md", "CONTRIBUTING.md", "SECURITY.md",
    "docs/ARCHITECTURE.md", "docs/RELEASING.md", "tools/package_source.py",
)
MACOS_FILES = (
    "settings.py", "browser_state.py", "login.py", "scheduling.py", "engine.py", "claim.py",
    "launcher.py", "location_access.py", "install.py", "requirements.txt",
    "README.md", "USER_GUIDE.md", "ARCHITECTURE.md", "TESTING.md", "AGENT_HANDOFF.md",
    "docs/architecture.svg", "docs/architecture.mmd", "docs/mermaid-config.json",
    "tests/test_engine.py", "tests/test_schedule.py", "tests/test_runtime.py", "tests/test_location.py",
)
WINDOWS_FILES = (
    "settings.py", "win_platform.py", "scheduling.py", "dialogs.py", "browser_state.py", "engine.py",
    "claim.py", "login.py", "location_access.py", "launcher.py", "task_scheduler.py", "install.py",
    "requirements.txt", "install.cmd", "README.md", "WINDOWS_VALIDATION.md", "AGENT_HANDOFF.md",
    "tests/test_engine.py", "tests/test_windows.py",
)
PREFIX = "guanaitong-claim-helper"


def public_files(root):
    names = list(ROOT_FILES) + ["macos/" + n for n in MACOS_FILES] + ["windows/" + n for n in WINDOWS_FILES]
    if (root / "LICENSE").is_file():names.append("LICENSE")
    result = {}
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("Invalid public source file: " + name)
        data = path.read_bytes()
        if (str(Path.home()).encode() in data or re.search(rb"[/]Users[/][^/\s]+", data)
                or re.search(rb"[A-Za-z]:[\\/]Users[\\/]", data)):
            raise ValueError("Machine-specific user path: " + name)
        if re.search(rb"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{20,}\b", data):
            raise ValueError("Potential credential marker: " + name)
        result[name] = data
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    checksum = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or checksum.exists():
        raise FileExistsError("Output exists; choose a new file name")
    files = public_files(root)
    manifest = {"format": 1, "license_included": "LICENSE" in files,
        "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(files.items())]}
    files["PACKAGE_MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + "/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with checksum.open("x", encoding="utf-8") as handle:handle.write(f"{digest}  {output.name}\n")
    print(json.dumps({"archive": str(output), "files": len(files), "bytes": output.stat().st_size,
                      "sha256": digest, "license_included": "LICENSE" in files}, ensure_ascii=False))


if __name__ == "__main__":
    main()
