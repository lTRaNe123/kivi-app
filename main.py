# main.py
import threading
import re
import textwrap
from collections import defaultdict

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
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition

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


def format_form_lines_as_table(lines) -> str:
    """
    Форматирует строки формы в стабильную текстовую таблицу.

    Бэкенд сейчас отдаёт строки вида:
    "1. Название | Шт. | 100 руб. | категория: II"
    """
    if not lines:
        return "Нет данных для отображения"

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

        rows.append((number, name, unit, price, category))

    widths = {
        "number": 4,
        "name": 46,
        "unit": 8,
        "price": 12,
        "category": 10,
    }

    border = (
        "+"
        + "-" * widths["number"]
        + "+"
        + "-" * widths["name"]
        + "+"
        + "-" * widths["unit"]
        + "+"
        + "-" * widths["price"]
        + "+"
        + "-" * widths["category"]
        + "+"
    )

    def row(number, name, unit, price, category):
        name_lines = textwrap.wrap(name, widths["name"]) or [""]
        out = []
        for line_idx, name_part in enumerate(name_lines):
            out.append(
                "|"
                + (number if line_idx == 0 else "").ljust(widths["number"])
                + "|"
                + name_part.ljust(widths["name"])
                + "|"
                + (unit if line_idx == 0 else "").ljust(widths["unit"])
                + "|"
                + (price if line_idx == 0 else "").ljust(widths["price"])
                + "|"
                + (category if line_idx == 0 else "").ljust(widths["category"])
                + "|"
            )
        return out

    table = [
        border,
        *row("№", "Наименование", "Ед.", "Цена", "Категория"),
        border,
    ]

    for item in rows:
        table.extend(row(*item))
        table.append(border)

    return "\n".join(table)


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
        self.ids.lines_text.text = ""

    def on_pre_enter(self, *args) -> None:
        """При заходе на экран подгружаем форму."""
        if self._code:
            self.load_form()

    def load_form(self) -> None:
        """Запрашиваем данные формы у API и заполняем таблицу."""
        lines_text = self.ids.lines_text
        lines_text.text = "Загружаем данные..."
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
                    self.ids.lines_text.text = ""
                    self.header_text = ""
                    self.error_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.header_text = data.get("header") or ""
                # поддержим и 'lines', и 'rows', если бэкенд вернёт так
                lines = data.get("lines") or data.get("rows") or []

                self.ids.lines_text.text = format_form_lines_as_table(lines)

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
