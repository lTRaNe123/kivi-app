from pathlib import Path


SYSTEM_ICONS = {
    "back": "navigation/back_{theme}.png",
    "chevron_right": "navigation/chevron_right_{theme}.png",
    "copy": "actions/copy_{theme}.png",
    "close": "actions/close_{theme}.png",
    "gift": "actions/gift_{theme}.png",
    "promo_code": "payment/promo_code_{theme}.png",
    "ruble": "payment/ruble_{theme}.png",
    "ct_coin": "payment/ct_coin_{theme}.png",
}

CATEGORY_ICONS = {
    "my_orders": "categories/my_orders.png",
    "uniform": "categories/uniform.png",
    "gear": "categories/gear.png",
    "chevrons": "categories/chevrons.png",
}

REQUIRED_ICON_NAMES = tuple(SYSTEM_ICONS) + tuple(CATEGORY_ICONS)
BASE_DIR = Path("assets/icons")


def _clean_theme(theme):
    return "light" if str(theme).lower() == "light" else "dark"


def system_icon_path(name, theme="dark"):
    pattern = SYSTEM_ICONS.get(name)
    if not pattern:
        return ""
    return str(BASE_DIR / pattern.format(theme=_clean_theme(theme)))


def category_icon_path(name):
    path = CATEGORY_ICONS.get(name)
    return str(BASE_DIR / path) if path else ""


def icon_path(name, theme="dark"):
    if name in CATEGORY_ICONS:
        return category_icon_path(name)
    return system_icon_path(name, theme)


def runtime_icon_paths():
    paths = []
    for name in SYSTEM_ICONS:
        paths.append(system_icon_path(name, "dark"))
        paths.append(system_icon_path(name, "light"))
    for name in CATEGORY_ICONS:
        paths.append(category_icon_path(name))
    return tuple(paths)


def category_icon_names():
    return tuple(CATEGORY_ICONS.keys())
