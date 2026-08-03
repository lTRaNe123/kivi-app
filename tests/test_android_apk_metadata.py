from pathlib import Path
import unittest

import hashlib

from android_apk_metadata import (
    ApkMetadataValidationError,
    archive_package_info_signature_flags,
    installed_package_info_signature_flags,
    package_info_signature_flags,
    package_signature_fingerprints,
    package_signature_fingerprints_with_source,
    validate_apk_metadata,
)


ROOT = Path(__file__).resolve().parents[1]


class FakePackageInfo:
    def __init__(
        self,
        package_name="org.vangelagency.strigmobile",
        version_code=9,
        signing_info=None,
        signatures=None,
    ):
        self.packageName = package_name
        self.versionCode = version_code
        self._long_version_code = version_code
        self.signingInfo = signing_info
        self.signatures = signatures

    def getLongVersionCode(self):
        return self._long_version_code


class FakePackageManager:
    GET_SIGNATURES = 64
    GET_SIGNING_CERTIFICATES = 134217728


class FakeSigningInfo:
    def __init__(self, signers):
        self._signers = signers

    def getApkContentsSigners(self):
        return self._signers


class FakeSignature:
    def __init__(self, der_bytes):
        self._der_bytes = der_bytes

    def toByteArray(self):
        return self._der_bytes


class FakeAndroid10ArchivePackageManager:
    def getPackageArchiveInfo(self, _path, flags):
        combined = FakePackageManager.GET_SIGNATURES | FakePackageManager.GET_SIGNING_CERTIFICATES
        if flags == FakePackageManager.GET_SIGNING_CERTIFICATES:
            return FakePackageInfo(signing_info=None, signatures=None)
        if flags == combined:
            return FakePackageInfo(signing_info=None, signatures=[FakeSignature(b"archive-cert")])
        return FakePackageInfo(signing_info=None, signatures=None)


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

    def test_api_27_uses_get_signatures_flag(self):
        self.assertEqual(
            package_info_signature_flags(FakePackageManager, 27),
            FakePackageManager.GET_SIGNATURES,
        )
        self.assertEqual(
            archive_package_info_signature_flags(FakePackageManager, 27),
            FakePackageManager.GET_SIGNATURES,
        )
        self.assertEqual(
            installed_package_info_signature_flags(FakePackageManager, 27),
            FakePackageManager.GET_SIGNATURES,
        )

    def test_api_28_plus_uses_get_signing_certificates_flag(self):
        self.assertEqual(
            package_info_signature_flags(FakePackageManager, 28),
            FakePackageManager.GET_SIGNING_CERTIFICATES,
        )
        self.assertEqual(
            package_info_signature_flags(FakePackageManager, 33),
            FakePackageManager.GET_SIGNING_CERTIFICATES,
        )

    def test_api_29_archive_uses_combined_signature_flags(self):
        self.assertEqual(
            archive_package_info_signature_flags(FakePackageManager, 29),
            FakePackageManager.GET_SIGNATURES | FakePackageManager.GET_SIGNING_CERTIFICATES,
        )

    def test_api_29_installed_uses_get_signing_certificates_flag(self):
        self.assertEqual(
            installed_package_info_signature_flags(FakePackageManager, 29),
            FakePackageManager.GET_SIGNING_CERTIFICATES,
        )

    def test_api_29_archive_with_only_get_signing_certificates_reproduces_missing_signing_info(self):
        pm = FakeAndroid10ArchivePackageManager()
        info = pm.getPackageArchiveInfo("vosk.apk", FakePackageManager.GET_SIGNING_CERTIFICATES)
        self.assertIsNone(info.signingInfo)
        self.assertIsNone(info.signatures)
        with self.assertRaises(ApkMetadataValidationError):
            package_signature_fingerprints(info, sdk_int=29, source_label="downloaded")

    def test_api_29_archive_with_combined_flags_gets_signatures_fallback(self):
        pm = FakeAndroid10ArchivePackageManager()
        flags = archive_package_info_signature_flags(FakePackageManager, 29)
        info = pm.getPackageArchiveInfo("vosk.apk", flags)
        fingerprints, source = package_signature_fingerprints_with_source(
            info,
            sdk_int=29,
            source_label="downloaded",
        )
        self.assertEqual(source, "signatures")
        self.assertEqual(fingerprints, {hashlib.sha256(b"archive-cert").hexdigest()})

    def test_main_gets_downloaded_archive_with_archive_flags(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("archive = pm.getPackageArchiveInfo(path, archive_flags)", main_py)
        self.assertNotIn("getPackageArchiveInfo(path, 0)", main_py)

    def test_main_gets_installed_package_with_installed_flags(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("installed = pm.getPackageInfo(PACKAGE_NAME, installed_flags)", main_py)

    def test_signing_info_none_with_signatures_fallback_passes(self):
        fingerprints, source = package_signature_fingerprints_with_source(
            FakePackageInfo(signing_info=None, signatures=[FakeSignature(b"legacy-cert")]),
            sdk_int=33,
            source_label="downloaded",
        )
        self.assertEqual(source, "signatures")
        self.assertEqual(fingerprints, {hashlib.sha256(b"legacy-cert").hexdigest()})

    def test_get_apk_contents_signers_none_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            package_signature_fingerprints(
                FakePackageInfo(signing_info=FakeSigningInfo(None), signatures=None),
                sdk_int=33,
                source_label="downloaded",
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-signature-check")

    def test_empty_signature_array_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            package_signature_fingerprints(
                FakePackageInfo(signing_info=FakeSigningInfo([]), signatures=[]),
                sdk_int=33,
                source_label="downloaded",
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-signature-check")

    def test_api_27_empty_signature_array_is_apk_validation_error(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            package_signature_fingerprints(
                FakePackageInfo(signatures=[]),
                sdk_int=27,
                source_label="installed",
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")
        self.assertEqual(ctx.exception.stage, "android-signature-check")

    def test_same_certificates_pass_as_equal_fingerprints(self):
        cert = b"cert-one"
        left = package_signature_fingerprints(
            FakePackageInfo(signing_info=FakeSigningInfo([FakeSignature(cert)])),
            sdk_int=33,
            source_label="installed",
        )
        right = package_signature_fingerprints(
            FakePackageInfo(signing_info=FakeSigningInfo([FakeSignature(cert)])),
            sdk_int=33,
            source_label="downloaded",
        )
        self.assertEqual(left, right)
        self.assertEqual(left, {hashlib.sha256(cert).hexdigest()})

    def test_different_certificates_are_rejected_by_set_compare(self):
        installed = package_signature_fingerprints(
            FakePackageInfo(signing_info=FakeSigningInfo([FakeSignature(b"cert-one")])),
            sdk_int=33,
            source_label="installed",
        )
        downloaded = package_signature_fingerprints(
            FakePackageInfo(signing_info=FakeSigningInfo([FakeSignature(b"cert-two")])),
            sdk_int=33,
            source_label="downloaded",
        )
        self.assertNotEqual(installed, downloaded)

    def test_multiple_certificate_order_does_not_matter(self):
        one = FakeSignature(b"cert-one")
        two = FakeSignature(b"cert-two")
        installed = package_signature_fingerprints(
            FakePackageInfo(signing_info=FakeSigningInfo([one, two])),
            sdk_int=33,
            source_label="installed",
        )
        downloaded = package_signature_fingerprints(
            FakePackageInfo(signing_info=FakeSigningInfo([two, one])),
            sdk_int=33,
            source_label="downloaded",
        )
        self.assertEqual(installed, downloaded)

    def test_signature_check_errors_are_not_default_download_errors(self):
        with self.assertRaises(ApkMetadataValidationError) as ctx:
            package_signature_fingerprints(
                FakePackageInfo(signing_info=FakeSigningInfo(None)),
                sdk_int=33,
                source_label="downloaded",
            )
        self.assertEqual(ctx.exception.label, "apk-validation-error")

    def test_installer_launch_is_after_apk_validation(self):
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        install_start = main_py.index("def install_update")
        verify_call = main_py.index("self._verify_downloaded_apk", install_start)
        installer_call = main_py.index("self._open_android_installer", install_start)
        self.assertLess(verify_call, installer_call)


if __name__ == "__main__":
    unittest.main()
