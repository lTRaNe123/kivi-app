import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def mobile_update_screen_block():
    text = (ROOT / "ui.kv").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^<MobileUpdateScreen>:\n(.*?)(?=^<[^>\n]+>:\n)", text)
    if not match:
        raise AssertionError("MobileUpdateScreen KV rule was not found")
    return match.group(1)


class MobileUpdateScreenKvTests(unittest.TestCase):
    def test_update_screen_avoids_layout_loop_widgets(self):
        block = mobile_update_screen_block()
        for forbidden in ("FinePrint", "CardBox", "AdaptiveCard", "ScrollView"):
            self.assertNotIn(forbidden, block)

    def test_update_screen_avoids_dynamic_height_bindings(self):
        block = mobile_update_screen_block()
        for forbidden in (
            "height: self.minimum_height",
            "height: self.texture_size",
            "self.texture_size[1]",
            "text_size: self.size",
            "texture_update",
            "do_layout",
        ):
            self.assertNotIn(forbidden, block)

    def test_progress_label_has_fixed_height(self):
        block = mobile_update_screen_block()
        progress_label = re.search(
            r"(?ms)Label:\n(?:(?!\n\s*\w).)*?text: root\.progress_text(?P<body>.*?)(?=\n\s*(?:Label|ProgressBar|Widget|Button|BoxLayout):)",
            block,
        )
        self.assertIsNotNone(progress_label)
        self.assertIn("size_hint_y: None", progress_label.group(0))
        self.assertRegex(progress_label.group(0), r"height:\s*dp\(28\)")


if __name__ == "__main__":
    unittest.main()
