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


def archive_package_info_signature_flags(package_manager, sdk_int):
    if int(sdk_int) >= 28:
        return int(package_manager.GET_SIGNATURES | package_manager.GET_SIGNING_CERTIFICATES)
    return int(package_manager.GET_SIGNATURES)


def installed_package_info_signature_flags(package_manager, sdk_int):
    if int(sdk_int) >= 28:
        return int(package_manager.GET_SIGNING_CERTIFICATES)
    return int(package_manager.GET_SIGNATURES)


def package_info_signature_flags(package_manager, sdk_int):
    return installed_package_info_signature_flags(package_manager, sdk_int)


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


def _as_non_empty_list(signatures):
    if signatures is None:
        return []
    signatures = list(signatures)
    return signatures


def _signing_info_signature_objects(signing_info):
    if signing_info is None:
        return []

    try:
        has_multiple = bool(signing_info.hasMultipleSigners())
    except Exception:
        has_multiple = False
    if has_multiple:
        return _as_non_empty_list(signing_info.getApkContentsSigners())

    try:
        history = _as_non_empty_list(signing_info.getSigningCertificateHistory())
    except Exception:
        history = []
    if history:
        return history

    return _as_non_empty_list(signing_info.getApkContentsSigners())


def package_signature_objects_with_source(package_info, *, sdk_int, source_label):
    if package_info is None:
        raise ApkMetadataValidationError(
            f"Android не вернул PackageInfo для {source_label} APK",
            stage="android-package-info",
        )

    if int(sdk_int) >= 28:
        signing_info = getattr(package_info, "signingInfo", None)
        signatures = _signing_info_signature_objects(signing_info)
        if signatures:
            return signatures, "signingInfo"

    signatures = _as_non_empty_list(getattr(package_info, "signatures", None))
    if signatures:
        return signatures, "signatures"

    raise ApkMetadataValidationError(
        f"Android не вернул сертификаты подписи для {source_label} APK",
        stage="android-signature-check",
    )


def package_signature_objects(package_info, *, sdk_int, source_label):
    signatures, _source = package_signature_objects_with_source(
        package_info,
        sdk_int=sdk_int,
        source_label=source_label,
    )
    return signatures


def package_signature_fingerprints_with_source(package_info, *, sdk_int, source_label):
    signatures, source = package_signature_objects_with_source(
        package_info,
        sdk_int=sdk_int,
        source_label=source_label,
    )
    return {signature_sha256_hex(signature) for signature in signatures}, source


def package_signature_fingerprints(package_info, *, sdk_int, source_label):
    fingerprints, _source = package_signature_fingerprints_with_source(
        package_info,
        sdk_int=sdk_int,
        source_label=source_label,
    )
    return fingerprints


def package_signing_info_exists(package_info, sdk_int):
    if package_info is None:
        return False
    if int(sdk_int) >= 28:
        return getattr(package_info, "signingInfo", None) is not None
    return getattr(package_info, "signatures", None) is not None


def package_legacy_signatures_exists(package_info):
    signatures = getattr(package_info, "signatures", None) if package_info is not None else None
    return bool(_as_non_empty_list(signatures))
