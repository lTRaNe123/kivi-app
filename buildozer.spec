[app]
title = ВОСК
package.name = strigmobile
package.domain = org.vangelagency
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,ttf,json
source.exclude_dirs = venv,__pycache__,.git
version = 0.1.14
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,REQUEST_INSTALL_PACKAGES
android.allow_cleartext = True
android.api = 35
android.minapi = 24
android.archs = arm64-v8a
android.numeric_version = 15
android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.12.0
android.add_resources = android_resources

[buildozer]
log_level = 2
warn_on_root = 1
