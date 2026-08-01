from pathlib import Path
import unittest

from android_apk_metadata import ApkMetadataValidationError, validate_apk_metadata


ROOT = Path(__file__).resolve().parents[1]


class FakePackageInfo:
    def __init__(self, package_name="org.vangelagency.strigmobile", version_code=9):
        self.packageName = package_name
        self.versionCode = version_code
        self._long_version_code = version_code

    def getLongVersionCode(self):
        return self._long_version_code


class AndroidApkMetadataTests(unittest.TestCase):
    def test_project_uses_build_version_nested_class(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("Build.VERSION", main_py)
        self.assertIn('autoclass("android.os.Build$VERSION")', main_py)

    def test_sdk_27_uses_version_code(self):
        package_info = FakePackageInfo(version_code=9)
        package_info._long_version_code = 99
        code = validate_apk_metadata(
            package_info,
            expected_package="org.vangelagency.strigmobile",
            expected_version_code=9,
            current_version_code=7,
            sdk_int=27,
        )
        self.assertEqual(code, 9)

    def test_sdk_28_uses_get_long_version_code(self):
        package_info = FakePackageInfo(version_code=1)
        package_info._long_version_code = 9
        code = validate_apk_metadata(
            package_info,
            expected_package="org.vangelagency.strigmobile",
            expected_version_code=9,
            current_version_code=7,
            sdk_int=28,
        )
        self.assertEqual(code, 9)

    def test_sdk_33_uses_get_long_version_code(self):
        package_info = FakePackageInfo(version_code=1)
        package_info._long_version_code = 9
        code = validate_apk_metadata(
            package_info,
            expected_package="org.vangelagency.strigmobile",
            expected_version_code=9,
            current_version_code=7,
            sdk_int=33,
        )
        self.assertEqual(code, 9)

    def test_missing_package_info_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            validate_apk_metadata(
                None,
                expected_package="org.vangelagency.strigmobile",
                expected_version_code=9,
                current_version_code=7,
                sdk_int=33,
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-package-info")

    def test_wrong_package_name_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            validate_apk_metadata(
                FakePackageInfo(package_name="org.example.bad", version_code=9),
                expected_package="org.vangelagency.strigmobile",
                expected_version_code=9,
                current_version_code=7,
                sdk_int=33,
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-package-name")

    def test_wrong_version_code_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            validate_apk_metadata(
                FakePackageInfo(version_code=8),
                expected_package="org.vangelagency.strigmobile",
                expected_version_code=9,
                current_version_code=7,
                sdk_int=33,
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-version-code")

    def test_old_version_code_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            validate_apk_metadata(
                FakePackageInfo(version_code=7),
                expected_package="org.vangelagency.strigmobile",
                expected_version_code=7,
                current_version_code=7,
                sdk_int=33,
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-version-code")

    def test_valid_metadata_passes(self):
        code = validate_apk_metadata(
            FakePackageInfo(version_code=9),
            expected_package="org.vangelagency.strigmobile",
            expected_version_code=9,
            current_version_code=7,
            sdk_int=33,
        )
        self.assertEqual(code, 9)


if __name__ == "__main__":
    unittest.main()
