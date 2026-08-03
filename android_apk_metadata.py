import hashlib


class ApkMetadataValidationError(ValueError):
    def __init__(self, message, *, stage="android-package-info"):
        super().__init__(message)
        self.label = "apk-validation-error"
        self.stage = stage


def version_code_from_package_info(package_info, sdk_int):
    if int(sdk_int) >= 28:
        return int(package_info.getLongVersionCode())
    return int(package_info.versionCode)


def validate_apk_metadata(package_info, *, expected_package, expected_version_code, current_version_code, sdk_int):
    if package_info is None:
        raise ApkMetadataValidationError(
            "Android не распознал файл как APK",
            stage="android-package-info",
        )

    if str(package_info.packageName) != expected_package:
        raise ApkMetadataValidationError(
            "Package name APK не совпадает",
            stage="android-package-name",
        )

    archive_code = version_code_from_package_info(package_info, sdk_int)
    expected_code = int(expected_version_code or 0)
    if archive_code != expected_code:
        raise ApkMetadataValidationError(
            "Version code APK не совпадает с сервером",
            stage="android-version-code",
        )
    if archive_code <= int(current_version_code or 0):
        raise ApkMetadataValidationError(
            "APK не новее текущей версии",
            stage="android-version-code",
        )
    return archive_code


def package_info_signature_flags(package_manager, sdk_int):
    if int(sdk_int) >= 28:
        return package_manager.GET_SIGNING_CERTIFICATES
    return package_manager.GET_SIGNATURES


def _java_bytes_to_bytes(raw):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    return bytes((int(value) & 0xFF for value in raw))


def signature_sha256_hex(signature):
    raw = _java_bytes_to_bytes(signature.toByteArray())
    if raw is None:
        raise ApkMetadataValidationError(
            "Android вернул пустой сертификат подписи APK",
            stage="android-signature-check",
        )
    return hashlib.sha256(raw).hexdigest()


def package_signature_objects(package_info, *, sdk_int, source_label):
    if package_info is None:
        raise ApkMetadataValidationError(
            f"Android не вернул PackageInfo для {source_label} APK",
            stage="android-package-info",
        )

    if int(sdk_int) >= 28:
        signing_info = getattr(package_info, "signingInfo", None)
        if signing_info is None:
            raise ApkMetadataValidationError(
                f"Android не вернул signingInfo для {source_label} APK",
                stage="android-signature-check",
            )
        signatures = signing_info.getApkContentsSigners()
    else:
        signatures = getattr(package_info, "signatures", None)

    if signatures is None:
        raise ApkMetadataValidationError(
            f"Android вернул пустой массив подписей для {source_label} APK",
            stage="android-signature-check",
        )

    signatures = list(signatures)
    if not signatures:
        raise ApkMetadataValidationError(
            f"Android вернул 0 сертификатов подписи для {source_label} APK",
            stage="android-signature-check",
        )
    return signatures


def package_signature_fingerprints(package_info, *, sdk_int, source_label):
    signatures = package_signature_objects(
        package_info,
        sdk_int=sdk_int,
        source_label=source_label,
    )
    return {signature_sha256_hex(signature) for signature in signatures}


def package_signing_info_exists(package_info, sdk_int):
    if package_info is None:
        return False
    if int(sdk_int) >= 28:
        return getattr(package_info, "signingInfo", None) is not None
    return getattr(package_info, "signatures", None) is not None
