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
