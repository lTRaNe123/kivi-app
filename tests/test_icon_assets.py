import re
import struct
from pathlib import Path
import unittest

from icon_assets import (
    REQUIRED_ICON_NAMES,
    category_icon_names,
    category_icon_path,
    icon_path,
    runtime_icon_paths,
    system_icon_path,
)


ROOT = Path(__file__).resolve().parents[1]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_color_type(path):
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise AssertionError(f"{path} is not a PNG")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, bit_depth, color_type


class IconAssetsTests(unittest.TestCase):
    def test_required_runtime_icon_paths_exist(self):
        names = set(REQUIRED_ICON_NAMES)
        self.assertEqual(
            names,
            {
                "back",
                "chevron_right",
                "copy",
                "close",
                "promo_code",
                "ruble",
                "ct_coin",
                "gift",
                "my_orders",
                "uniform",
                "gear",
                "chevrons",
            },
        )
        for rel_path in runtime_icon_paths():
            path = ROOT / rel_path
            self.assertTrue(path.is_file(), rel_path)

    def test_png_assets_open_and_have_alpha(self):
        for rel_path in runtime_icon_paths():
            width, height, bit_depth, color_type = _png_color_type(ROOT / rel_path)
            self.assertGreater(width, 0, rel_path)
            self.assertGreater(height, 0, rel_path)
            self.assertEqual(bit_depth, 8, rel_path)
            self.assertIn(color_type, {4, 6}, rel_path)

    def test_icon_paths_are_relative_and_local(self):
        for rel_path in runtime_icon_paths():
            self.assertFalse(Path(rel_path).is_absolute(), rel_path)
            self.assertFalse(rel_path.startswith(("http://", "https://")), rel_path)
            self.assertNotIn("design/icon_system_prototype", rel_path)

    def test_no_runtime_code_refs_design_prototype(self):
        for rel_path in ("main.py", "ui.kv", "icon_assets.py"):
            text = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotIn("design/icon_system_prototype", text)

    def test_no_external_icon_urls_in_runtime_code(self):
        for rel_path in ("main.py", "ui.kv", "icon_assets.py"):
            text = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"https?://")

    def test_helper_selects_light_and_dark_system_icons(self):
        self.assertEqual(
            system_icon_path("back", "dark"),
            "assets/icons/navigation/back_dark.png",
        )
        self.assertEqual(
            system_icon_path("back", "light"),
            "assets/icons/navigation/back_light.png",
        )
        self.assertEqual(icon_path("close", "light"), "assets/icons/actions/close_light.png")
        self.assertEqual(icon_path("ct_coin"), "assets/icons/payment/ct_coin_dark.png")

    def test_category_icons_are_not_theme_recolored(self):
        for name in category_icon_names():
            self.assertEqual(icon_path(name, "light"), category_icon_path(name))
            self.assertEqual(icon_path(name, "dark"), category_icon_path(name))
            self.assertNotRegex(category_icon_path(name), r"_(light|dark)\.png$")

    def test_changed_rows_use_icon_source_not_letter_badges(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('"icon_source": category_icon_path(', main_py)
        self.assertIn('"icon_source": category_icon_path("chevrons")', main_py)
        for forbidden in (
            '"orders": "З"',
            '"uniform": "Ф"',
            '"equipment": "С"',
            '"icon_text": "Ш"',
        ):
            self.assertNotIn(forbidden, main_py)

    def test_kv_uses_helper_for_new_runtime_icons(self):
        kv = (ROOT / "ui.kv").read_text(encoding="utf-8")
        for name in ("back", "chevron_right", "close", "ct_coin", "ruble"):
            self.assertRegex(kv, rf'icon_path\("{re.escape(name)}"')
        self.assertNotIn("assets/icons/chevron_right.png", kv)

    def test_buildozer_includes_png_assets(self):
        spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
        self.assertRegex(spec, r"source\.include_exts\s*=.*\bpng\b")
        self.assertRegex(spec, r"source\.exclude_dirs\s*=.*\bdesign\b")


if __name__ == "__main__":
    unittest.main()
