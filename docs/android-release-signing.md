# Android Release Signing

Первый постоянный APK для встроенных обновлений должен быть release-сборкой. Все будущие APK с тем же `package.name` и `package.domain` подписываются тем же постоянным ключом.

Правила:

- `package.name` и `package.domain` менять нельзя.
- `version_code` всегда увеличивается.
- `APP_VERSION_CODE` и `android.numeric_version` должны совпадать.
- Ключ, пароль keystore и пароль alias нельзя хранить в Git.
- Debug APK не является постоянным каналом обновлений.
- При переходе с debug APK на release APK может потребоваться один раз удалить debug-версию с устройства.

Безопасная сборка release APK должна брать секреты только из переменных окружения:

- `VOSK_KEYSTORE_PATH`
- `VOSK_KEYSTORE_PASSWORD`
- `VOSK_KEY_ALIAS`
- `VOSK_KEY_PASSWORD`

Перед публикацией APK нужно проверить, что он подписан тем же сертификатом, что и уже установленная постоянная версия приложения.

