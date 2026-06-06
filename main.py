# main.py
import threading
import re
import webbrowser
from collections import defaultdict
from urllib.parse import quote

from kivy.app import App
from kivy.clock import Clock

Clock.max_iteration = 1000

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    ObjectProperty,
    StringProperty,
    ListProperty,
    NumericProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle

from api_client import api_client, ApiError


# ---------- утилиты интерфейса ----------


def make_inventory_label(text: str) -> Label:
    """
    Многострочная подпись (Label), которая:
    - растягивается по ширине родителя
    - переносит текст по ширине
    - автоматически подбирает высоту по контенту
    """
    lbl = Label(
        text=text,
        size_hint_y=None,
        size_hint_x=1,
        halign="left",
        valign="top",
    )

    def _on_width(instance, value):
        instance.text_size = (value, None)

    def _on_texture_size(instance, size):
        instance.height = size[1] + dp(6)

    lbl.bind(width=_on_width, texture_size=_on_texture_size)
    return lbl


def parse_form_lines(lines):
    """
    Разбирает строки формы в табличные записи.

    Бэкенд сейчас отдаёт строки вида:
    "1. Название | Шт. | 100 руб. | категория: II"
    """
    rows = []
    for idx, raw_line in enumerate(lines, start=1):
        raw = str(raw_line).strip()
        parts = [part.strip() for part in raw.split("|")]

        number = str(idx)
        name = raw
        unit = ""
        price = ""
        category = ""

        if parts:
            match = re.match(r"^(\d+)[\.\)]?\s*(.*)$", parts[0])
            if match:
                number = match.group(1)
                name = match.group(2).strip()
            else:
                name = parts[0]

        if len(parts) > 1:
            unit = parts[1]
        if len(parts) > 2:
            price = parts[2]
        if len(parts) > 3:
            category = parts[3].replace("категория:", "").strip()

        search_href = f"{api_client.cfg.base_url}/?search={quote(name)}" if name else ""
        category_href = f"{api_client.cfg.base_url}/?category={quote(category)}" if category else ""

        rows.append({
            "number": number,
            "name": {
                "text": name,
                "href": search_href,
            },
            "unit": unit,
            "price": price,
            "category": {
                "text": category,
                "href": category_href,
            },
        })

    return rows


def escape_markup(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("[", "&bl;")
        .replace("]", "&br;")
    )


class TableCell(Label):
    href = StringProperty("")

    def on_touch_up(self, touch):
        if self.href and self.collide_point(*touch.pos):
            webbrowser.open(self.href)
            return True
        return super().on_touch_up(touch)


class TableSeparator(Widget):
    pass


def add_table_cell(row, text, width, height=38, bold=False, align="center", href=""):
    display = escape_markup(text)
    if href:
        display = f"[u][color=0645AD]{display}[/color][/u]"

    row.add_widget(TableCell(
        text=display,
        width=dp(width),
        height=dp(height),
        bold=bold,
        halign=align,
        markup=True,
        href=str(href or ""),
    ))


def normalize_columns(table, fallback_rows):
    columns = table.get("columns") if isinstance(table, dict) else None
    if isinstance(columns, list) and columns:
        out = []
        for col in columns:
            if isinstance(col, dict):
                key = str(col.get("key") or col.get("id") or col.get("title") or "")
                title = str(col.get("title") or col.get("label") or key)
                width = int(col.get("width") or 130)
                align = str(col.get("align") or "center")
                if key:
                    out.append((key, title, width, align))
        if out:
            return out

    return [
        ("number", "№", 60, "center"),
        ("name", "Наименование", 520, "left"),
        ("unit", "Ед.", 110, "center"),
        ("price", "Цена", 140, "center"),
        ("category", "Категория", 150, "center"),
    ]


def normalize_rows(table, lines):
    rows = table.get("rows") if isinstance(table, dict) else None
    if isinstance(rows, list):
        return rows
    return parse_form_lines(lines)


def get_cell_value(row_data, key):
    if isinstance(row_data, dict):
        cells = row_data.get("cells")
        if isinstance(cells, dict) and key in cells:
            cell = cells[key]
        else:
            cell = row_data.get(key, "")
    else:
        cell = ""

    if isinstance(cell, dict):
        return cell.get("text") or cell.get("value") or "", cell.get("href") or cell.get("url") or ""
    return cell, ""


def get_row_text(row_data, key):
    value, _href = get_cell_value(row_data, key)
    return str(value or "")


def get_row_href(row_data, key):
    _value, href = get_cell_value(row_data, key)
    return str(href or "")


def make_site_list_button(text):
    return Button(
        text=str(text or ""),
        size_hint_y=None,
        height=dp(52),
        background_normal="",
        background_color=(0.86, 0.86, 0.86, 1),
        color=(0.25, 0.25, 0.25, 1),
        font_size="15sp",
    )


def set_widget_background(widget, rgba):
    with widget.canvas.before:
        Color(*rgba)
        rect = Rectangle(pos=widget.pos, size=widget.size)

    def update_rect(instance, _value):
        rect.pos = instance.pos
        rect.size = instance.size

    widget.bind(pos=update_rect, size=update_rect)


def make_detail_table_data(item):
    name = get_row_text(item, "name")
    unit = get_row_text(item, "unit")
    price = get_row_text(item, "price")
    category = get_row_text(item, "category")

    return {
        "meta": {
            "name": name,
            "unit": unit,
            "price": price,
            "category": category,
        },
    }


def open_material_popup(item):
    detail = make_detail_table_data(item)
    meta = detail["meta"]

    root = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(14))
    set_widget_background(root, (1, 1, 1, 1))

    title_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
    title_row.add_widget(Label(
        text="Информация",
        color=(0.25, 0.25, 0.25, 1),
        halign="left",
        valign="middle",
        text_size=(dp(760), dp(38)),
        font_size="20sp",
    ))
    root.add_widget(title_row)

    info = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(196))
    info_rows = [
        ("Наименование материальных ценностей", meta["name"]),
        ("Единица измерения", meta["unit"]),
        ("Цена за единицу", meta["price"]),
        ("Категория", meta["category"]),
    ]
    for label, value in info_rows:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(46))
        add_table_cell(row, label, 340, 46, align="center")
        add_table_cell(row, value, 620, 46, align="center")
        info.add_widget(row)
    root.add_widget(info)

    root.add_widget(Label(
        text="Полная история движения открывается на сайте.",
        color=(0.25, 0.25, 0.25, 1),
        size_hint_y=None,
        height=dp(44),
        font_size="15sp",
        halign="center",
        valign="middle",
        text_size=(dp(900), dp(44)),
    ))

    footer = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
    site_href = get_row_href(item, "name")
    btn_site = Button(text="Открыть на сайте", disabled=not bool(site_href))
    btn_close = Button(text="Закрыть")
    footer.add_widget(btn_site)
    footer.add_widget(btn_close)
    root.add_widget(footer)

    popup = Popup(
        title="",
        content=root,
        size_hint=(0.78, 0.52),
        auto_dismiss=True,
    )

    if site_href:
        btn_site.bind(on_release=lambda *_args: webbrowser.open(site_href))
    btn_close.bind(on_release=lambda *_args: popup.dismiss())
    popup.open()


def render_form_catalog(container, data) -> None:
    container.clear_widgets()
    container.spacing = dp(12)
    container.padding = [dp(36), dp(10), dp(36), dp(10)]
    container.width = dp(1100)
    table = data.get("table") if isinstance(data, dict) else None
    lines = []
    if isinstance(data, dict):
        lines = data.get("lines") or data.get("rows") or []
    rows = normalize_rows(table, lines)

    if not rows:
        status = make_site_list_button("Нет данных для отображения")
        status.disabled = True
        container.add_widget(status)
        return

    for row_data in rows:
        name = get_row_text(row_data, "name")
        if not name:
            continue
        btn = make_site_list_button(name)
        btn.width = dp(980)
        btn.size_hint_x = None
        btn.bind(on_release=lambda _btn, item=row_data: open_material_popup(item))
        container.add_widget(btn)


def render_form_table(container, data) -> None:
    """Рисует форму как визуальную таблицу, а не как консольный текст."""
    container.clear_widgets()
    container.spacing = 0
    container.padding = [0, 0, 0, 0]

    table = data.get("table") if isinstance(data, dict) else None
    lines = []
    if isinstance(data, dict):
        lines = data.get("lines") or data.get("rows") or []
    rows = normalize_rows(table, lines)
    if not rows:
        status_row = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(720),
            height=dp(42),
        )
        add_table_cell(status_row, "Нет данных для отображения", 720, 42)
        container.add_widget(status_row)
        return

    columns = normalize_columns(table if isinstance(table, dict) else {}, rows)
    total_width = sum(col[2] for col in columns)
    container.width = dp(total_width)

    header = BoxLayout(
        orientation="horizontal",
        size_hint=(None, None),
        width=dp(total_width),
        height=dp(54),
    )
    for _key, title, width, align in columns:
        add_table_cell(header, title, width, 54, bold=True)
    container.add_widget(header)

    container.add_widget(TableSeparator(
        size_hint=(None, None),
        width=dp(total_width),
        height=dp(5),
    ))

    for row_data in rows:
        row_type = row_data.get("type") if isinstance(row_data, dict) else ""
        if row_type == "separator":
            container.add_widget(TableSeparator(
                size_hint=(None, None),
                width=dp(total_width),
                height=dp(5),
            ))
            continue

        row_height = int(row_data.get("height") or 42) if isinstance(row_data, dict) else 42
        name_value, _href = get_cell_value(row_data, "name")
        if len(str(name_value)) > 42:
            row_height = max(row_height, 64)

        row = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(total_width),
            height=dp(row_height),
        )
        for key, _title, width, align in columns:
            value, href = get_cell_value(row_data, key)
            add_table_cell(row, value, width, row_height, align=align, href=href)
        container.add_widget(row)


def build_inventory_from_docs(docs):
    """
    Превращаем список ПРИНЯТЫХ накладных в агрегированный инвентарь:

    docs: [
      {
        "nid": ...,
        "status": "ACCEPTED",
        "items": [
          { "iid": 1, "name": "Лопата", "qty": 1, "unit": "шт" },
          ...
        ]
      },
      ...
    ]

    => [
      { "iid": 1, "name": "Лопата", "unit": "шт", "qty": 3 },
      ...
    ]
    """
    agg = defaultdict(lambda: {"iid": None, "name": "", "unit": "", "qty": 0.0})

    for doc in docs:
        items = doc.get("items") or []
        for item in items:
            iid = item.get("iid")
            name = (item.get("name") or "").strip()
            unit = (item.get("unit") or "").strip()
            key = (iid, name, unit)

            rec = agg[key]
            rec["iid"] = iid
            rec["name"] = name
            rec["unit"] = unit

            try:
                qty = float(item.get("qty") or 0)
            except (TypeError, ValueError):
                qty = 0.0
            rec["qty"] += qty

    return list(agg.values())


# ---------- ЭКРАН ВХОДА ----------


class LoginScreen(Screen):
    login_input = ObjectProperty(None)
    password_input = ObjectProperty(None)
    message = StringProperty("")

    def do_login(self):
        username = (self.login_input.text or "").strip()
        password = (self.password_input.text or "").strip()

        if not username or not password:
            self.message = "Введите логин и пароль"
            return

        self.message = "Входим..."

        def worker():
            try:
                user = api_client.login(username, password)
            except Exception as exc:
                msg = f"Ошибка входа: {exc}"

                def ui_fail(dt, msg=msg):
                    self.message = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt):
                app = App.get_running_app()
                app.current_user = user
                self.manager.current = "user_home"

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()


# ---------- ГЛАВНЫЙ ЭКРАН ПОЛЬЗОВАТЕЛЯ ----------


class UserHomeScreen(Screen):
    status_text = StringProperty("")

    def on_pre_enter(self, *args):
        app = App.get_running_app()
        user = app.current_user or {}

        full_name = f"{user.get('name','')} {user.get('otec','')}".strip()
        if not full_name:
            full_name = user.get("username", "")

        self.ids.lbl_user_name.text = full_name or "Военнослужащий"

        rank = (user.get("rank_fact") or "").strip()
        position = (user.get("position") or "").strip()
        battery = (user.get("battery") or "").strip()

        info_lines = []
        if rank:
            info_lines.append(rank)
        if position:
            info_lines.append(position)
        if battery:
            info_lines.append(battery)

        self.ids.lbl_user_info.text = "\n".join(info_lines) or "Информация о должности"

        self.refresh_lists()

    def refresh_lists(self):
        box_pending = self.ids.box_pending
        box_accepted = self.ids.box_accepted

        box_pending.clear_widgets()
        box_accepted.clear_widgets()
        box_pending.add_widget(make_inventory_label("Загружаем накладные с сервера..."))
        self.status_text = ""

        def worker():
            try:
                assignments = api_client.get_assignments()
            except Exception as exc:
                msg = f"Ошибка загрузки: {exc}"

                def ui_fail(dt, msg=msg):
                    box_pending.clear_widgets()
                    box_pending.add_widget(make_inventory_label(msg))

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt):
                self._fill_lists(assignments)

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _fill_lists(self, assignments):
        box_pending = self.ids.box_pending
        box_accepted = self.ids.box_accepted

        box_pending.clear_widgets()
        box_accepted.clear_widgets()

        pending_docs = [a for a in assignments if a.get("status") == "PENDING"]
        accepted_docs = [a for a in assignments if a.get("status") == "ACCEPTED"]

        inventory = build_inventory_from_docs(accepted_docs)

        # --- ожидают подтверждения ---
        if not pending_docs:
            box_pending.add_widget(
                make_inventory_label("Нет накладных для подтверждения")
            )
        else:
            for doc in pending_docs:
                lines = []

                num = (doc.get("num") or "").strip()
                if num:
                    lines.append(f"Накладная №{num}")

                dname = (doc.get("name") or "").strip()
                if dname:
                    lines.append(dname)

                if doc.get("date_nak"):
                    lines.append(f"Дата: {doc['date_nak']}")

                items = doc.get("items") or []
                if items:
                    lines.append("Состав:")
                    for item in items:
                        iname = (item.get("name") or "").strip()
                        qty = item.get("qty") or ""
                        unit = (item.get("unit") or "").strip()
                        lines.append(f"  • {iname}: {qty} {unit}")

                text = "\n".join(lines) if lines else "Накладная"
                box_pending.add_widget(make_inventory_label(text))

        # --- мой инвентарь по накладным ---
        if not inventory:
            box_accepted.add_widget(
                make_inventory_label("Закреплённого имущества пока нет")
            )
        else:
            for idx, item in enumerate(inventory, start=1):
                name = item["name"] or "Предмет"
                qty = item["qty"]
                unit = item["unit"] or ""
                line = f"{idx}. {name} — {qty} {unit}"
                box_accepted.add_widget(make_inventory_label(line))

    def goto_transfers(self):
        self.manager.current = "transfers"

    def goto_forms(self):
        self.manager.current = "forms_menu"


# ---------- ЭКРАН: СПИСОК ПЕРЕДАЧ ----------


class TransferListScreen(Screen):
    incoming_box = ObjectProperty(None)
    outgoing_box = ObjectProperty(None)
    status_text = StringProperty("")

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.incoming_box.clear_widgets()
        self.outgoing_box.clear_widgets()
        self.incoming_box.add_widget(
            make_inventory_label("Загружаем список передач...")
        )
        self.status_text = ""

        def worker():
            try:
                incoming, outgoing = api_client.get_transfer_lists()
            except Exception as exc:
                msg = f"Ошибка: {exc}"

                def ui_fail(dt, msg=msg):
                    self.incoming_box.clear_widgets()
                    self.outgoing_box.clear_widgets()
                    self.incoming_box.add_widget(make_inventory_label(msg))
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, incoming=incoming, outgoing=outgoing):
                self._fill_lists(incoming, outgoing)

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _fill_lists(self, incoming, outgoing):
        self.incoming_box.clear_widgets()
        self.outgoing_box.clear_widgets()

        # --- входящие ---
        if not incoming:
            self.incoming_box.add_widget(
                make_inventory_label("Нет входящих передач")
            )
        else:
            for tr in incoming:
                tid = tr.get("tid")
                header = f"#{tid} от {tr.get('from_label','')}".strip()
                status = tr.get("status", "")
                comment = tr.get("comment") or ""

                lines = [header]
                if comment:
                    lines.append(f"Комментарий: {comment}")
                if status:
                    lines.append(f"Статус: {status}")

                items = tr.get("items") or []
                if items:
                    lines.append("Состав:")
                    for it in items:
                        name = it.get("name") or ""
                        qty = it.get("qty") or ""
                        unit = it.get("unit") or ""
                        lines.append(f"  • {name}: {qty} {unit}")

                self.incoming_box.add_widget(make_inventory_label("\n".join(lines)))

                # кнопки принять/отклонить
                if tid is not None and status == "NEW":
                    btn_row = BoxLayout(
                        size_hint_y=None, height=dp(36), spacing=dp(6)
                    )
                    btn_ok = Button(text="Принять")
                    btn_rej = Button(text="Отклонить")

                    def make_cb(action):
                        def cb(instance, tid_local=tid, action_local=action):
                            self.confirm_transfer(tid_local, action_local)

                        return cb

                    btn_ok.bind(on_release=make_cb("accept"))
                    btn_rej.bind(on_release=make_cb("reject"))
                    btn_row.add_widget(btn_ok)
                    btn_row.add_widget(btn_rej)
                    self.incoming_box.add_widget(btn_row)

        # --- исходящие ---
        if not outgoing:
            self.outgoing_box.add_widget(
                make_inventory_label("Нет исходящих передач")
            )
        else:
            for tr in outgoing:
                tid = tr.get("tid")
                header = f"#{tid} для {tr.get('to_label','')}".strip()
                status = tr.get("status", "")
                comment = tr.get("comment") or ""

                lines = [header]
                if comment:
                    lines.append(f"Комментарий: {comment}")
                if status:
                    lines.append(f"Статус: {status}")

                items = tr.get("items") or []
                if items:
                    lines.append("Состав:")
                    for it in items:
                        name = it.get("name") or ""
                        qty = it.get("qty") or ""
                        unit = it.get("unit") or ""
                        lines.append(f"  • {name}: {qty} {unit}")

                self.outgoing_box.add_widget(make_inventory_label("\n".join(lines)))

    def confirm_transfer(self, tid: int, action: str):
        self.status_text = f"Отправляем решение по передаче #{tid}..."

        def worker():
            try:
                api_client.confirm_transfer(tid, action)
            except Exception as exc:
                msg = f"Ошибка: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt):
                self.status_text = "Решение отправлено"
                self.refresh()

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def goto_create(self):
        self.manager.current = "transfer_create"

    def goto_home(self):
        self.manager.current = "user_home"


# ---------- ЭКРАН: СОЗДАНИЕ ПЕРЕДАЧИ ----------


class TransferCreateScreen(Screen):
    receiver_spinner = ObjectProperty(None)
    comment_input = ObjectProperty(None)
    item_name_input = ObjectProperty(None)
    item_qty_input = ObjectProperty(None)
    item_unit_input = ObjectProperty(None)

    status_text = StringProperty("")
    users_labels = ListProperty([])
    users_ids = ListProperty([])
    selected_to_uid = NumericProperty(0)

    def on_pre_enter(self, *args):
        if not self.users_ids:
            self.load_users()

    def load_users(self):
        self.status_text = "Загружаем список людей..."

        def worker():
            try:
                users = api_client.get_users()
            except Exception as exc:
                msg = f"Ошибка загрузки пользователей: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            labels = []
            ids = []
            for u in users:
                uid = int(u.get("uid"))
                username = u.get("username") or ""
                name = u.get("name") or ""
                otec = u.get("otec") or ""
                label = f"{uid}. {username} {name} {otec}".strip()
                labels.append(label)
                ids.append(uid)

            def ui_ok(dt, labels=labels, ids=ids):
                self.users_labels = labels
                self.users_ids = ids
                if labels:
                    self.receiver_spinner.values = labels
                    self.receiver_spinner.text = "выберите получателя"
                self.status_text = ""

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def on_receiver_selected(self, text):
        if text in self.users_labels:
            idx = self.users_labels.index(text)
            self.selected_to_uid = int(self.users_ids[idx])
        else:
            self.selected_to_uid = 0

    def send_transfer(self):
        to_uid = int(self.selected_to_uid or 0)
        comment = (self.comment_input.text or "").strip()
        name = (self.item_name_input.text or "").strip()
        qty_text = (self.item_qty_input.text or "").strip()
        unit = (self.item_unit_input.text or "").strip() or "шт"

        if to_uid <= 0:
            self.status_text = "Выберите получателя"
            return

        if not name:
            self.status_text = "Укажите название предмета"
            return

        try:
            qty = float(qty_text.replace(",", ".")) if qty_text else 0.0
        except ValueError:
            self.status_text = "Количество должно быть числом"
            return

        if qty <= 0:
            self.status_text = "Количество должно быть > 0"
            return

        items = [
            {
                "name": name,
                "qty": qty,
                "unit": unit,
            }
        ]

        self.status_text = "Отправляем передачу..."

        def worker():
            try:
                tid = api_client.create_transfer(to_uid, comment, items)
            except Exception as exc:
                msg = f"Ошибка создания передачи: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, tid=tid):
                self.status_text = f"Передача #{tid} создана"
                self.comment_input.text = ""
                self.item_name_input.text = ""
                self.item_qty_input.text = ""
                self.item_unit_input.text = ""

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def goto_list(self):
        self.manager.current = "transfers"


# ---------- ЭКРАН: МЕНЮ КНИГ / ФОРМ ----------


class FormsMenuScreen(Screen):
    """
    Экран выбора книги/формы:
    - Книга №10
    - Вечерняя поверка
    - Спальное расположение
    - Штатка
    """

    def open_form(self, code: str, title: str) -> None:
        """
        code  — короткий код формы (f10, evening, sleep, shtatka, ...),
        title — человекочитаемое название для заголовка экрана.
        """
        app = App.get_running_app()
        view = app.root.get_screen("form_view")
        view.set_code_and_title(code, title)
        app.root.current = "form_view"


# ---------- ЭКРАН: ПРОСМОТР КОНКРЕТНОЙ ФОРМЫ ----------


class FormViewScreen(Screen):
    """
    Экран просмотра конкретной формы/книги.

    Ожидает ответ form_view.php вида:
    {
      "success": true,
      "title":  "Версия 0.2",
      "header": "Вечерняя поверка",
      "lines": [
         "1 Ряд. Глушков В.В.  ...",
         "2 Ряд. Соян А.Н.     ...",
         ...
      ]
    }
    """

    title_text = StringProperty("")   # верхний заголовок (например, "Книга №10")
    header_text = StringProperty("")  # подзаголовок ("Вечерняя поверка", "Штатка" и т.п.)
    error_text = StringProperty("")   # текст ошибки
    _code = StringProperty("")        # внутренний код формы (f10, evening ...)

    def set_code_and_title(self, code: str, title: str) -> None:
        """Вызывается из FormsMenuScreen при выборе формы."""
        self._code = code
        self.title_text = title
        self.header_text = ""
        self.error_text = ""
        self.ids.lines_table.clear_widgets()

    def on_pre_enter(self, *args) -> None:
        """При заходе на экран подгружаем форму."""
        if self._code:
            self.load_form()

    def load_form(self) -> None:
        """Запрашиваем данные формы у API и заполняем таблицу."""
        table = self.ids.lines_table
        table.clear_widgets()
        status_row = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(720),
            height=dp(42),
        )
        add_table_cell(status_row, "Загружаем данные...", 720, 42)
        table.add_widget(status_row)
        self.error_text = ""
        self.header_text = ""

        if not self._code:
            self.error_text = "Код формы не задан"
            return

        def worker():
            try:
                data = api_client.get_form(self._code)
            except Exception as exc:
                msg = f"Ошибка загрузки: {exc}"

                def ui_fail(dt, msg=msg):
                    self.ids.lines_table.clear_widgets()
                    self.header_text = ""
                    self.error_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.header_text = data.get("header") or ""
                if self._code in ("f10", "book10"):
                    render_form_catalog(self.ids.lines_table, data)
                else:
                    render_form_table(self.ids.lines_table, data)

                self.error_text = ""

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()


# ---------- ROOT & APP ----------


class RootWidget(ScreenManager):
    pass


class SixnerInventoryApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_user = None

    def build(self):
        self.title = "Учёт имущества"
        Builder.load_file("ui.kv")
        sm = RootWidget(transition=FadeTransition())
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(UserHomeScreen(name="user_home"))
        sm.add_widget(TransferListScreen(name="transfers"))
        sm.add_widget(TransferCreateScreen(name="transfer_create"))
        sm.add_widget(FormsMenuScreen(name="forms_menu"))
        sm.add_widget(FormViewScreen(name="form_view"))
        return sm


if __name__ == "__main__":
    SixnerInventoryApp().run()
