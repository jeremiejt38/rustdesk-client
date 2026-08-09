#!/usr/bin/env python3
"""Apply a build-config.json to the rustdesk-client source tree.

Usage:
    python build-config.py path/to/build-config.json
"""

import json
import re
import shutil
import sys
from pathlib import Path


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def patch_common_rs(root: Path, config: dict) -> None:
    conn = config.get("connection", {})
    common_rs = root / "src" / "common.rs"
    text = common_rs.read_text()

    replacements = {
        "const DEFAULT_HOST: &str = ": conn.get("server_id", "relay.akasha.ing"),
        "const DEFAULT_RELAY: &str = ": conn.get("relay_server", "relay.akasha.ing"),
        "const DEFAULT_API: &str = ": conn.get("api_server", "https://rust.akasha.ing"),
        "const DEFAULT_KEY: &str = ": conn.get("public_key", ""),
    }

    for prefix, value in replacements.items():
        pattern = re.compile(rf"({re.escape(prefix)}).+?;")
        text = pattern.sub(rf'\1"{value}";', text)

    common_rs.write_text(text)


def patch_cargo_toml(root: Path, config: dict) -> None:
    branding = config.get("branding", {})
    app_name = branding.get("app_name", "RustDesk")
    company = branding.get("company_name", "Purslane Tech Pte. Ltd.")

    cargo_toml = root / "Cargo.toml"
    text = cargo_toml.read_text()

    text = re.sub(
        r'description = "RustDesk Remote Desktop"',
        f'description = "{app_name}"',
        text,
    )
    text = re.sub(
        r'ProductName = "RustDesk"',
        f'ProductName = "{app_name}"',
        text,
    )
    text = re.sub(
        r'FileDescription = "RustDesk Remote Desktop"',
        f'FileDescription = "{app_name}"',
        text,
    )
    text = re.sub(
        r'OriginalFilename = "rustdesk\\.exe"',
        f'OriginalFilename = "{app_name}.exe"',
        text,
    )
    text = re.sub(
        r'LegalCopyright = "Copyright .*? All rights reserved\\."',
        f'LegalCopyright = "Copyright {company}. All rights reserved."',
        text,
    )
    cargo_toml.write_text(text)

    portable_cargo = root / "libs" / "portable" / "Cargo.toml"
    if portable_cargo.exists():
        text = portable_cargo.read_text()
        text = re.sub(
            r'description = "RustDesk Remote Desktop"',
            f'description = "{app_name}"',
            text,
        )
        text = re.sub(
            r'ProductName = "RustDesk"',
            f'ProductName = "{app_name}"',
            text,
        )
        text = re.sub(
            r'FileDescription = "RustDesk Remote Desktop"',
            f'FileDescription = "{app_name}"',
            text,
        )
        portable_cargo.write_text(text)


def patch_default_settings(root: Path, config: dict) -> None:
    """Inject default/override settings into hbb_common config.rs."""
    # This is a minimal placeholder; a full implementation would map all
    # security/network/display/ui keys to DEFAULT_SETTINGS / OVERWRITE_SETTINGS.
    pass


def patch_icons(root: Path, config: dict) -> None:
    """Replace default icon/logo files when custom assets are provided."""
    branding = config.get("branding", {})
    icon = branding.get("icon_path", "")
    logo = branding.get("logo_path", "")

    res_dir = root / "res"
    if icon and Path(icon).exists() and (res_dir / "icon.png").exists():
        shutil.copy(icon, res_dir / "icon.png")
    if logo and Path(logo).exists() and (res_dir / "logo.png").exists():
        shutil.copy(logo, res_dir / "logo.png")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build-config.py <build-config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)
    root = Path(__file__).resolve().parent

    patch_common_rs(root, config)
    patch_cargo_toml(root, config)
    patch_icons(root, config)
    patch_default_settings(root, config)

    print("Build config applied.")


if __name__ == "__main__":
    main()
