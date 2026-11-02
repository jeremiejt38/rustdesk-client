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


_VALID_CONN_TYPES = {"incoming", "outgoing"}
# Keys that must never be baked as plain options: the permanent password is
# handled by the hard_settings password/salt mechanism, not a raw option.
_SKIP_OPTION_KEYS = {"password", "salt"}
_OPTION_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def _rust_string(value: str) -> str:
    """Escape a value for a Rust string literal; control chars are stripped."""
    clean = "".join(c for c in value if c not in "\n\r\t" and ord(c) >= 0x20)
    return clean.replace("\\", "\\\\").replace('"', '\\"')


def _rust_map_literal(pairs: dict[str, str]) -> str:
    items = ", ".join(
        f'("{_rust_string(k)}".to_string(), "{_rust_string(v)}".to_string())'
        for k, v in sorted(pairs.items())
    )
    return f"RwLock::new(HashMap::from([{items}]))"


def _clean_settings(raw: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (raw or {}).items():
        key = str(key)
        if key in _SKIP_OPTION_KEYS or not _OPTION_KEY_RE.match(key):
            continue
        if value is None:
            continue
        out[key] = str(value)[:256]
    return out


def _patch_settings_map(text: str, name: str, pairs: dict[str, str]) -> str:
    if not pairs:
        return text
    pattern = re.compile(
        rf"(pub static ref {name}: RwLock<HashMap<String, String>> = )[^;]+;"
    )
    literal = _rust_map_literal(pairs)
    new_text, count = pattern.subn(lambda m: m.group(1) + literal + ";", text)
    if count != 1:
        print(f"warning: {name} initializer not patched ({count} matches)")
    return new_text


def patch_default_settings(root: Path, config: dict) -> None:
    """Bake profile settings into the client's compile-time setting maps.

    - ui["conn-type"] -> HARD_SETTINGS (the "appearance" switch: incoming =
      support-client screen only, outgoing = remote-control input only).
    - security + network + ui + presets + recording -> OVERWRITE_SETTINGS
      (admin-enforced options the end user cannot change).
    - display -> DEFAULT_DISPLAY_SETTINGS (defaults the user can change).
    """
    config_rs = root / "libs" / "hbb_common" / "src" / "config.rs"
    text = config_rs.read_text()

    ui = config.get("ui") or {}
    conn_type = ui.get("conn-type")
    if conn_type and conn_type in _VALID_CONN_TYPES:
        text = _patch_settings_map(text, "HARD_SETTINGS", {"conn-type": conn_type})
    elif conn_type:
        print(f"warning: ignoring invalid conn-type {conn_type!r}")

    overwrite: dict[str, str] = {}
    for group in ("security", "network", "ui", "presets", "recording"):
        overwrite.update(_clean_settings(config.get(group) or {}))
    overwrite.pop("conn-type", None)
    text = _patch_settings_map(text, "OVERWRITE_SETTINGS", overwrite)

    display = _clean_settings(config.get("display") or {})
    text = _patch_settings_map(text, "DEFAULT_DISPLAY_SETTINGS", display)

    config_rs.write_text(text)


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
