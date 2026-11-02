#!/usr/bin/env python3
"""Standalone checks for build-config.py patching.

Run with: python tests/test_build_config.py  (exits non-zero on failure)
Uses a minimal config.rs fixture — no real tree, no pytest dependency.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
spec = importlib.util.spec_from_file_location(
    "build_config", Path(__file__).resolve().parent.parent / "build-config.py"
)
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)

CONFIG_RS = """\
lazy_static::lazy_static! {
    pub static ref HARD_SETTINGS: RwLock<HashMap<String, String>> = Default::default();
    pub static ref OVERWRITE_SETTINGS: RwLock<HashMap<String, String>> = Default::default();
}
"""


def make_root(tmp: Path) -> Path:
    cfg = tmp / "libs" / "hbb_common" / "src"
    cfg.mkdir(parents=True)
    (cfg / "config.rs").write_text(CONFIG_RS, encoding="utf-8")
    return tmp


def test_escaping() -> None:
    """Quotes, backslashes and newlines cannot escape the literal."""
    literal = bc._rust_map_literal({'a"b\\c\nd': "v"})
    assert "\\\\" in literal and '\\"' in literal
    assert "\n" not in literal


def test_inject_and_repatch_fails() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d))
        bc.patch_default_settings(root, {"ui": {"conn-type": "incoming"}})
        text = (root / "libs/hbb_common/src/config.rs").read_text(encoding="utf-8")
        assert '"conn-type".to_string(), "incoming".to_string()' in text
        # Second run on an already-patched tree must fail loudly.
        try:
            bc.patch_default_settings(root, {"ui": {"conn-type": "incoming"}})
        except RuntimeError:
            pass
        else:
            raise AssertionError("re-patch did not raise")


def test_invalid_conn_type_exits() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d))
        try:
            bc.patch_default_settings(root, {"ui": {"conn-type": "bogus"}})
        except SystemExit as e:
            assert e.code == 1
        else:
            raise AssertionError("invalid conn-type did not exit")


def test_missing_initializer_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d))
        cfg = root / "libs/hbb_common/src/config.rs"
        cfg.write_text(CONFIG_RS.replace("Default::default()", "RwLock::new(x)"), encoding="utf-8")
        try:
            bc.patch_default_settings(root, {"ui": {"conn-type": "incoming"}})
        except RuntimeError:
            pass
        else:
            raise AssertionError("missing initializer did not raise")


if __name__ == "__main__":
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        fn()
        print(f"ok {name}")
    print("all build-config checks passed")
