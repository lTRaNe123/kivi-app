[app]
title = Strig
package.name = strigmobile
package.domain = org.vangelagency
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,ttf,json
source.exclude_dirs = venv,__pycache__,.git
version = 0.1.0
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.allow_cleartext = True
android.api = 35
android.minapi = 24
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
