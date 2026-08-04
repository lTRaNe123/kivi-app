import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from android_fileprovider_paths import (
    PROVIDER_PATHS_RESOURCE,
    FileProviderPathError,
    expected_update_provider_root,
    provider_authority,
    validate_update_apk_provider_path,
)


ROOT = Path(__file__).resolve().parents[1]
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


class AndroidFileProviderPathTests(unittest.TestCase):
    def test_fileprovider_xml_allows_only_update_apk_files_path(self):
        xml_path = ROOT / "android_resources" / "xml" / "vosk_update_paths.xml"
        root = ET.parse(xml_path).getroot()
        files_paths = [
            node
            for node in root
            if node.tag.endswith("files-path")
            and (node.attrib.get(ANDROID_NS + "name") or node.attrib.get("name")) == "update_apks"
            and (node.attrib.get(ANDROID_NS + "path") or node.attrib.get("path")) == "cache/updates/"
        ]
        self.assertEqual(len(files_paths), 1)

    def test_actual_update_apk_path_is_inside_allowed_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            apk_path = Path(tmpdir) / "cache" / "updates" / "update.apk"
            apk_path.parent.mkdir(parents=True)
            apk_path.write_bytes(b"apk")
            info = validate_update_apk_provider_path(str(apk_path), user_data_dir=tmpdir)
            self.assertTrue(info["path_inside_provider_root"])
            self.assertEqual(
                info["expected_provider_root_canonical"],
                expected_update_provider_root(tmpdir),
            )

    def test_apk_outside_cache_updates_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            apk_path = Path(tmpdir) / "cache" / "other" / "update.apk"
            apk_path.parent.mkdir(parents=True)
            apk_path.write_bytes(b"apk")
            with self.assertRaises(FileProviderPathError):
                validate_update_apk_provider_path(str(apk_path), user_data_dir=tmpdir)

    def test_path_traversal_outside_cache_updates_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            apk_path = Path(tmpdir) / "outside.apk"
            apk_path.write_bytes(b"apk")
            traversal = Path(tmpdir) / "cache" / "updates" / ".." / ".." / "outside.apk"
            with self.assertRaises(FileProviderPathError):
                validate_update_apk_provider_path(str(traversal), user_data_dir=tmpdir)

    def test_non_apk_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "cache" / "updates" / "update.bin"
            file_path.parent.mkdir(parents=True)
            file_path.write_bytes(b"apk")
            with self.assertRaises(FileProviderPathError):
                validate_update_apk_provider_path(str(file_path), user_data_dir=tmpdir)

    def test_manifest_authority_and_paths_resource_match(self):
        provider_xml = (ROOT / "android_manifest" / "provider.xml").read_text(encoding="utf-8")
        self.assertIn('android:authorities="org.vangelagency.strigmobile.fileprovider"', provider_xml)
        self.assertIn('android:name="android.support.FILE_PROVIDER_PATHS"', provider_xml)
        self.assertIn(f'android:resource="{PROVIDER_PATHS_RESOURCE}"', provider_xml)
        self.assertEqual(
            provider_authority("org.vangelagency.strigmobile"),
            "org.vangelagency.strigmobile.fileprovider",
        )

    def test_installer_uses_content_uri_not_file_uri(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("FileProvider.getUriForFile(activity, provider_authority_text, apk_file)", main_py)
        self.assertIn('content_uri_text.startswith("content://")', main_py)
        self.assertNotIn("Uri.fromFile", main_py)
        self.assertNotIn("file://", main_py)

    def test_installer_mime_and_read_permission_flag_are_present(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('"application/vnd.android.package-archive"', main_py)
        self.assertIn("Intent.FLAG_GRANT_READ_URI_PERMISSION", main_py)
        self.assertIn("Intent.FLAG_ACTIVITY_NEW_TASK", main_py)

    def test_installer_launch_is_after_all_apk_validation(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        install_start = main_py.index("def install_update")
        verify_call = main_py.index("self._verify_downloaded_apk", install_start)
        installer_call = main_py.index("self._open_android_installer", install_start)
        self.assertLess(verify_call, installer_call)

    def test_fileprovider_errors_are_installer_launch_errors(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('label="installer-launch-error"', main_py)
        self.assertIn('stage=self._download_stage', main_py)


if __name__ == "__main__":
    unittest.main()
