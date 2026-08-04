import os


PROVIDER_PATHS_RESOURCE = "@xml/vosk_update_paths"
UPDATE_APK_PROVIDER_SUBDIR = os.path.join("cache", "updates")


class FileProviderPathError(ValueError):
    pass


def provider_authority(package_name):
    return f"{package_name}.fileprovider"


def expected_update_provider_root(user_data_dir):
    return os.path.realpath(os.path.join(user_data_dir, UPDATE_APK_PROVIDER_SUBDIR))


def validate_update_apk_provider_path(apk_path, *, user_data_dir):
    apk_canonical = os.path.realpath(apk_path)
    root_canonical = expected_update_provider_root(user_data_dir)

    if not os.path.isfile(apk_canonical):
        raise FileProviderPathError("APK файл для установки не найден")
    if os.path.splitext(apk_canonical)[1].lower() != ".apk":
        raise FileProviderPathError("Файл обновления должен иметь расширение .apk")

    try:
        inside_root = os.path.commonpath([root_canonical, apk_canonical]) == root_canonical
    except ValueError:
        inside_root = False
    if not inside_root:
        raise FileProviderPathError("APK находится вне разрешённого FileProvider каталога")

    return {
        "apk_canonical_path": apk_canonical,
        "expected_provider_root": os.path.join(user_data_dir, UPDATE_APK_PROVIDER_SUBDIR),
        "expected_provider_root_canonical": root_canonical,
        "path_inside_provider_root": True,
    }
