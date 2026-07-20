# main.py
import threading
import uuid
from collections import defaultdict

from kivy.app import App
from kivy.clock import Clock
from kivy.clock import Clock

Clock.max_iteration = 1000

from kivy.lang import Builder
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ObjectProperty,
    StringProperty,
    ListProperty,
    NumericProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.recycleview.views import RecycleDataViewBehavior

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
        color=(0.07, 0.07, 0.07, 1),
        padding=(dp(12), dp(10)),
    )

    def _on_width(instance, value):
        instance.text_size = (value, None)

    def _on_texture_size(instance, size):
        instance.height = size[1] + dp(20)

    lbl.bind(width=_on_width, texture_size=_on_texture_size)
    return lbl


def make_table_label(text: str, width: int) -> Label:
    lbl = Label(
        text=str(text),
        size_hint=(None, None),
        width=dp(width),
        halign="left",
        valign="middle",
        padding=(dp(8), dp(6)),
        color=(0.07, 0.07, 0.07, 1),
        font_size="13sp",
    )
    lbl.bind(
        width=lambda inst, value: setattr(inst, "text_size", (value - dp(16), None)),
        texture_size=lambda inst, size: setattr(inst, "height", max(dp(44), size[1] + dp(12))),
    )
    return lbl


CHEVRON_STATUS_LABELS = {
    "DRAFT": "Черновик",
    "WAITING_PAYMENT": "Ожидает оплаты",
    "PAID": "Оплачен",
    "IN_WORK": "В работе",
    "READY": "Готов",
    "DELIVERING": "Доставляется",
    "COMPLETED": "Завершён",
    "CANCELLED": "Отменён",
}

CHEVRON_STATUS_COLORS = {
    "DRAFT": [0.58, 0.58, 0.58, 1],
    "WAITING_PAYMENT": [0.86, 0.56, 0.20, 1],
    "PAID": [0.16, 0.48, 0.78, 1],
    "IN_WORK": [0.20, 0.42, 0.78, 1],
    "READY": [0.20, 0.55, 0.32, 1],
    "DELIVERING": [0.40, 0.34, 0.68, 1],
    "COMPLETED": [0.12, 0.44, 0.26, 1],
    "CANCELLED": [0.70, 0.20, 0.20, 1],
}


def chevron_status_label(status):
    return CHEVRON_STATUS_LABELS.get(status or "", status or "Неизвестно")


def chevron_status_color(status):
    return CHEVRON_STATUS_COLORS.get(status or "", [0.42, 0.42, 0.42, 1])


def chevron_price_text(payload):
    if not payload.get("price_available"):
        return "Стоимость не назначена"
    parts = []
    if payload.get("total_rub") is not None:
        parts.append(f"{payload.get('total_rub')} ₽")
    if payload.get("total_st") is not None:
        parts.append(f"{payload.get('total_st')} ST")
    return " / ".join(parts) if parts else "Стоимость не назначена"


class FinanceTableRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    cells = ListProperty([])
    row_data = ObjectProperty({})

    def refresh_view_attrs(self, rv, index, data):
        result = super().refresh_view_attrs(rv, index, data)
        self.cells = data.get("cells") or []
        self.row_data = data.get("row_data") or {}
        self._rebuild()
        return result

    def _rebuild(self):
        self.clear_widgets()
        self.orientation = "horizontal"
        self.size_hint = (None, None)
        self.height = dp(48)
        total_width = 0
        max_height = dp(48)
        for cell in self.cells:
            width = int(cell.get("width") or 120)
            lbl = make_table_label(cell.get("value", ""), width)
            self.add_widget(lbl)
            total_width += dp(width)
            max_height = max(max_height, lbl.height)
        self.width = total_width
        self.height = max_height

    def on_release(self):
        app = App.get_running_app()
        screen = app.root.get_screen("finance_account")
        screen.open_operation_detail(self.row_data)


class NavListRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    title = StringProperty("")
    subtitle = StringProperty("")
    icon_text = StringProperty("")
    action = StringProperty("")
    payload = ObjectProperty({})

    def refresh_view_attrs(self, rv, index, data):
        result = super().refresh_view_attrs(rv, index, data)
        self.title = data.get("title") or ""
        self.subtitle = data.get("subtitle") or ""
        self.icon_text = data.get("icon_text") or ""
        self.action = data.get("action") or ""
        self.payload = data.get("payload") or {}
        return result

    def on_release(self):
        app = App.get_running_app()
        screen = app.root.current_screen
        if hasattr(screen, "handle_nav_action"):
            screen.handle_nav_action(self.action, self.payload)


class ChevronKitItemRow(RecycleDataViewBehavior, BoxLayout):
    title = StringProperty("")
    meta = StringProperty("")
    image_url = StringProperty("")
    placeholder = StringProperty("ШЕВРОН")

    def refresh_view_attrs(self, rv, index, data):
        result = super().refresh_view_attrs(rv, index, data)
        self.title = data.get("title") or ""
        self.meta = data.get("meta") or ""
        self.image_url = data.get("image_url") or ""
        self.placeholder = data.get("placeholder") or "ШЕВРОН"
        return result


class ChevronOptionRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    group_code = StringProperty("")
    option_code = StringProperty("")
    title = StringProperty("")
    mark = StringProperty("")
    price_text = StringProperty("")
    selection_type = StringProperty("single")
    selected = BooleanProperty(False)
    option_disabled = BooleanProperty(False)

    def refresh_view_attrs(self, rv, index, data):
        result = super().refresh_view_attrs(rv, index, data)
        self.group_code = data.get("group_code") or ""
        self.option_code = data.get("option_code") or ""
        self.title = data.get("title") or ""
        self.mark = data.get("mark") or ""
        self.price_text = data.get("price_text") or ""
        self.selection_type = data.get("selection_type") or "single"
        self.selected = bool(data.get("selected"))
        self.option_disabled = bool(data.get("option_disabled"))
        return result

    def on_release(self):
        if self.option_disabled:
            return
        app = App.get_running_app()
        screen = app.root.current_screen
        if hasattr(screen, "toggle_option"):
            screen.toggle_option(self.group_code, self.option_code)


class ChevronNameLineRow(RecycleDataViewBehavior, BoxLayout):
    line_index = NumericProperty(0)
    text_value = StringProperty("")
    quantity = NumericProperty(1)

    def refresh_view_attrs(self, rv, index, data):
        result = super().refresh_view_attrs(rv, index, data)
        self.line_index = int(data.get("line_index") or index)
        self.text_value = data.get("text_value") or ""
        self.quantity = int(data.get("quantity") or 1)
        return result

    def _screen(self):
        app = App.get_running_app()
        return app.root.current_screen

    def edit_line(self):
        screen = self._screen()
        if hasattr(screen, "edit_line"):
            screen.edit_line(self.line_index)

    def remove_line(self):
        screen = self._screen()
        if hasattr(screen, "remove_line"):
            screen.remove_line(self.line_index)

    def increment(self, delta):
        screen = self._screen()
        if hasattr(screen, "change_quantity"):
            screen.change_quantity(self.line_index, delta)


class ChevronOrderListRow(RecycleDataViewBehavior, ButtonBehavior, BoxLayout):
    order_id = NumericProperty(0)
    order_number = StringProperty("")
    kit_title = StringProperty("")
    meta = StringProperty("")
    price_text = StringProperty("")
    status_text = StringProperty("")
    status_color = ListProperty([0.55, 0.55, 0.55, 1])

    def refresh_view_attrs(self, rv, index, data):
        result = super().refresh_view_attrs(rv, index, data)
        self.order_id = int(data.get("order_id") or 0)
        self.order_number = data.get("order_number") or ""
        self.kit_title = data.get("kit_title") or ""
        self.meta = data.get("meta") or ""
        self.price_text = data.get("price_text") or ""
        self.status_text = data.get("status_text") or ""
        self.status_color = data.get("status_color") or [0.55, 0.55, 0.55, 1]
        return result

    def on_release(self):
        app = App.get_running_app()
        screen = app.root.current_screen
        if hasattr(screen, "open_order"):
            screen.open_order(self.order_id)


def fill_cards(container, items):
    container.clear_widgets()
    for idx, item in enumerate(items, start=1):
        card = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(76),
            padding=(dp(14), dp(10)),
            spacing=dp(12),
        )
        card.canvas.before.clear()
        with card.canvas.before:
            Color(1, 1, 1, 1)
            card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
            Color(0.86, 0.86, 0.86, 1)
            card._border = Line(
                rounded_rectangle=(card.x, card.y, card.width, card.height, dp(8)),
                width=1,
            )

        def _sync_canvas(instance, *_):
            instance._bg.pos = instance.pos
            instance._bg.size = instance.size
            instance._border.rounded_rectangle = (
                instance.x,
                instance.y,
                instance.width,
                instance.height,
                dp(8),
            )

        card.bind(pos=_sync_canvas, size=_sync_canvas)
        card.add_widget(
            Label(
                text=str(idx),
                size_hint_x=None,
                width=dp(28),
                bold=True,
                color=(0.05, 0.05, 0.05, 1),
                font_size="18sp",
                halign="center",
                valign="middle",
                text_size=(dp(28), dp(56)),
            )
        )
        title = Label(
            text=item,
            bold=True,
            color=(0.05, 0.05, 0.05, 1),
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        card.add_widget(title)
        container.add_widget(card)


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

        access = int(user.get("access") or 0)
        access_shop = int(user.get("access_shop") or 0)
        position_sec = str(user.get("position_sec") or "")

        self.ids.btn_voentorg.disabled = access_shop != 1 and access != 1
        self.ids.btn_employee.disabled = not self._can_use_employee_panel(access, position_sec)

    def _can_use_employee_panel(self, access, position_sec):
        if access == 1:
            return True
        roles = ["Вышивальщик", "Вырезальщик", "Комплектовальщик", "Доставщик"]
        return any(role.lower() in position_sec.lower() for role in roles)

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

    def goto_finance(self):
        self.manager.current = "finance_account"

    def goto_voentorg(self):
        self.manager.current = "voentorg"

    def goto_employee_panel(self):
        self.manager.current = "employee_panel"


# ---------- ЭКРАН: ЛИЧНЫЙ КАБИНЕТ ----------


class FinanceAccountScreen(Screen):
    status_text = StringProperty("")
    balance_text = StringProperty("Баланс: -")
    page = NumericProperty(1)
    table_width = NumericProperty(dp(320))
    users_labels = ListProperty([])
    users_ids = ListProperty([])
    selected_to_uid = NumericProperty(0)
    current_columns = ListProperty([])
    current_rows = ListProperty([])

    def on_pre_enter(self, *args):
        self.page = 1
        self.refresh()
        if not self.users_ids:
            self.load_users()

    def refresh(self):
        query = (self.ids.search_input.text or "").strip()
        self.status_text = "Загружаем Личный кабинет..."

        def worker():
            try:
                data = api_client.get_finance_profile(query=query, page=int(self.page), limit=100)
            except Exception as exc:
                msg = f"Ошибка ЛК: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.fill_finance(data)

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def fill_finance(self, data):
        profile = data.get("profile") or {}
        table = data.get("table") or {}
        columns = table.get("columns") or []
        rows = table.get("rows") or []
        pagination = table.get("pagination") or {}

        balance = profile.get("balance")
        currency = profile.get("currency") or "ST"
        self.balance_text = f"Баланс: {balance} {currency}"
        self.current_columns = columns
        self.current_rows = rows

        self._build_header(columns)
        self._build_rows(columns, rows)

        total = pagination.get("total", len(rows))
        self.status_text = f"Операций: {total}"

    def _build_header(self, columns):
        header = self.ids.finance_header
        header.clear_widgets()
        total_width = 0
        for col in columns:
            width = int(col.get("width") or 120)
            lbl = make_table_label(col.get("title") or col.get("key") or "", width)
            lbl.bold = True
            header.add_widget(lbl)
            total_width += dp(width)
        header.width = total_width

    def _build_rows(self, columns, rows):
        table = self.ids.finance_table
        total_width = sum(dp(int(col.get("width") or 120)) for col in columns) or dp(320)
        self.table_width = total_width
        table.data = [
            {
                "cells": [
                    {
                        "value": row.get(col.get("key"), ""),
                        "width": int(col.get("width") or 120),
                    }
                    for col in columns
                ],
                "row_data": row,
            }
            for row in rows
        ]

    def load_users(self):
        def worker():
            try:
                users = api_client.get_users()
            except Exception:
                return

            labels = []
            ids = []
            for u in users:
                uid = int(u.get("uid"))
                if uid == api_client.user_id:
                    continue
                username = u.get("username") or ""
                name = u.get("name") or ""
                otec = u.get("otec") or ""
                labels.append(f"{uid}. {username} {name} {otec}".strip())
                ids.append(uid)

            def ui_ok(dt, labels=labels, ids=ids):
                self.users_labels = labels
                self.users_ids = ids
                self.ids.finance_receiver.values = labels

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def on_receiver_selected(self, text):
        if text in self.users_labels:
            self.selected_to_uid = int(self.users_ids[self.users_labels.index(text)])
        else:
            self.selected_to_uid = 0

    def send_transfer(self):
        amount = self._amount_from_input(self.ids.transfer_amount.text)
        comment = (self.ids.transfer_comment.text or "").strip()
        to_uid = int(self.selected_to_uid or 0)

        if to_uid <= 0:
            self.status_text = "Выберите получателя"
            return
        if amount <= 0:
            self.status_text = "Введите сумму перевода"
            return

        self.status_text = "Отправляем перевод..."

        def worker():
            try:
                api_client.create_finance_transfer(to_uid, amount, comment)
            except Exception as exc:
                msg = f"Ошибка перевода: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt):
                self.ids.transfer_amount.text = ""
                self.ids.transfer_comment.text = ""
                self.status_text = "Перевод выполнен"
                self.refresh()

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def send_withdraw(self):
        amount = self._amount_from_input(self.ids.withdraw_amount.text)
        comment = (self.ids.withdraw_comment.text or "").strip()

        if amount <= 0:
            self.status_text = "Введите сумму вывода"
            return

        self.status_text = "Создаём заявку на вывод..."

        def worker():
            try:
                api_client.create_finance_withdraw(amount, comment)
            except Exception as exc:
                msg = f"Ошибка вывода: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt):
                self.ids.withdraw_amount.text = ""
                self.ids.withdraw_comment.text = ""
                self.status_text = "Заявка на вывод создана"
                self.refresh()

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _amount_from_input(self, text):
        try:
            return float((text or "").replace(",", "."))
        except ValueError:
            return 0.0

    def open_operation_detail(self, row):
        lines = []
        for col in self.current_columns:
            key = col.get("key")
            title = col.get("title") or key
            lines.append(f"{title}: {row.get(key, '')}")
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        content.add_widget(make_inventory_label("\n".join(lines)))
        btn = Button(text="Закрыть", size_hint_y=None, height=dp(44))
        content.add_widget(btn)
        popup = Popup(title="Операция", content=content, size_hint=(0.92, 0.72))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    def goto_home(self):
        self.manager.current = "user_home"


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
        # очищаем прошлые строки
        self.ids.lines_grid.clear_widgets()

    def on_pre_enter(self, *args) -> None:
        """При заходе на экран подгружаем форму."""
        if self._code:
            self.load_form()

    def load_form(self) -> None:
        """Запрашиваем данные формы у API и заполняем таблицу."""
        grid = self.ids.lines_grid
        grid.clear_widgets()
        self.error_text = ""
        self.header_text = ""

        if not self._code:
            self.error_text = "Код формы не задан"
            return

        # временная надпись, пока грузим
        loading_lbl = Label(
            text="Загружаем данные...",
            size_hint_y=None,
            height=dp(24),
            halign="left",
            valign="middle",
        )
        loading_lbl.bind(
            size=lambda inst, *_: setattr(inst, "text_size", inst.size)
        )
        grid.add_widget(loading_lbl)

        def worker():
            try:
                data = api_client.get_form(self._code)
            except Exception as exc:
                msg = f"Ошибка загрузки: {exc}"

                def ui_fail(dt, msg=msg):
                    grid = self.ids.lines_grid
                    grid.clear_widgets()
                    self.header_text = ""
                    self.error_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                grid = self.ids.lines_grid
                grid.clear_widgets()

                self.header_text = data.get("header") or ""
                # поддержим и 'lines', и 'rows', если бэкенд вернёт так
                lines = data.get("lines") or data.get("rows") or []

                if not lines:
                    grid.add_widget(make_inventory_label("Нет данных для отображения"))
                else:
                    for line in lines:
                        grid.add_widget(make_inventory_label(str(line)))

                self.error_text = ""

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()


# ---------- БАЗОВЫЕ ЭКРАНЫ РАЗДЕЛОВ ----------


class VoentorgScreen(Screen):
    status_text = StringProperty("")

    def on_pre_enter(self, *args):
        self.load_menu()

    def load_menu(self):
        self.status_text = "Загружаем Военторг..."
        self.ids.voentorg_list.data = []

        def worker():
            try:
                sections = api_client.get_voentorg_menu()
            except Exception as exc:
                msg = f"Ошибка Военторга: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, sections=sections):
                self.ids.voentorg_list.data = [
                    {
                        "title": section.get("title") or "",
                        "subtitle": section.get("subtitle") or "",
                        "icon_text": section.get("icon") or "",
                        "action": section.get("code") or "",
                        "payload": section,
                    }
                    for section in sections
                ]
                self.status_text = ""

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def handle_nav_action(self, action, payload):
        if action == "chevrons":
            self.manager.current = "chevron_order"
            return
        if action == "orders":
            self.manager.current = "chevron_orders"
            return
        self.status_text = "Раздел будет подключен отдельной веткой Военторга."

    def goto_home(self):
        self.manager.current = "user_home"


class ChevronOrdersScreen(Screen):
    status_text = StringProperty("")
    active_status = StringProperty("")
    loading = BooleanProperty(False)
    page = NumericProperty(1)
    has_more = BooleanProperty(False)

    FILTERS = [
        ("", "Все"),
        ("DRAFT", "Черновики"),
        ("IN_WORK", "В работе"),
        ("READY", "Готовые"),
        ("COMPLETED", "Завершённые"),
    ]

    def on_pre_enter(self, *args):
        if not self.ids.orders_list.data:
            self.load_orders()

    def select_status(self, status):
        self.active_status = status
        self.page = 1
        self.load_orders()

    def load_orders(self):
        self.loading = True
        self.status_text = "Загружаем заказы..."
        self.ids.orders_list.data = []

        def worker():
            try:
                data = api_client.get_chevron_orders(self.active_status, page=1, limit=20)
            except Exception as exc:
                msg = f"Ошибка заказов: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.loading = False
                orders = data.get("orders") or []
                pagination = data.get("pagination") or {}
                self.page = int(pagination.get("page") or 1)
                self.has_more = bool(pagination.get("has_more"))
                self.ids.orders_list.data = [self._row_payload(order) for order in orders]
                self.status_text = "" if orders else "Заказов пока нет."

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def load_more(self):
        if self.loading or not self.has_more:
            return
        next_page = int(self.page) + 1
        self.loading = True
        self.status_text = "Загружаем ещё..."

        def worker():
            try:
                data = api_client.get_chevron_orders(self.active_status, page=next_page, limit=20)
            except Exception as exc:
                msg = f"Ошибка заказов: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.loading = False
                orders = data.get("orders") or []
                pagination = data.get("pagination") or {}
                self.page = int(pagination.get("page") or next_page)
                self.has_more = bool(pagination.get("has_more"))
                self.ids.orders_list.data = list(self.ids.orders_list.data) + [
                    self._row_payload(order) for order in orders
                ]
                self.status_text = ""

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _row_payload(self, order):
        created = (order.get("created_at") or "").split(" ")[0]
        lines_count = int(order.get("lines_count") or 0)
        return {
            "order_id": int(order.get("id") or 0),
            "order_number": order.get("order_number") or "",
            "kit_title": order.get("kit_title") or "",
            "meta": f"{created} · строк: {lines_count}",
            "price_text": chevron_price_text(order),
            "status_text": chevron_status_label(order.get("status")),
            "status_color": chevron_status_color(order.get("status")),
        }

    def open_order(self, order_id):
        detail = self.manager.get_screen("chevron_order_detail")
        detail.open_order(order_id)
        self.manager.current = "chevron_order_detail"

    def goto_voentorg(self):
        self.manager.current = "voentorg"


class ChevronOrderDetailScreen(Screen):
    order_id = NumericProperty(0)
    title_text = StringProperty("Заказ")
    status_text = StringProperty("")
    kit_text = StringProperty("")
    config_text = StringProperty("")
    lines_text = StringProperty("")
    payment_text = StringProperty("Способ оплаты: не выбран")
    price_text = StringProperty("Стоимость не назначена")
    error_text = StringProperty("")
    loading = BooleanProperty(False)
    is_draft = BooleanProperty(False)
    detail = ObjectProperty({})

    def open_order(self, order_id):
        self.order_id = int(order_id or 0)
        self.load_detail()

    def load_detail(self):
        if not self.order_id:
            self.error_text = "Заказ не выбран"
            return
        self.loading = True
        self.error_text = "Загружаем заказ..."

        def worker():
            try:
                data = api_client.get_chevron_order_detail(self.order_id)
            except Exception as exc:
                msg = f"Ошибка заказа: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.error_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.loading = False
                self.detail = data
                self._render_detail(data)

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _render_detail(self, data):
        order = data.get("order") or {}
        kit = data.get("kit") or {}
        options = data.get("options") or []
        lines = data.get("lines") or []
        status = order.get("status")
        self.title_text = order.get("order_number") or "Заказ"
        self.status_text = f"Статус: {chevron_status_label(status)}"
        created = order.get("created_at") or ""
        self.kit_text = f"Дата: {created}\nКомплект: {kit.get('title') or ''}"
        self.config_text = "\n".join(
            f"{option.get('group_title')}: {option.get('title')}" for option in options
        ) or "Параметры не найдены"
        self.lines_text = "\n".join(
            f"{line.get('text_value')} × {line.get('quantity')}" for line in lines
        ) or "Строки не найдены"
        self.payment_text = "Способ оплаты: " + (order.get("payment_method") or "не выбран")
        self.price_text = chevron_price_text(order)
        self.is_draft = status == "DRAFT"
        self.error_text = ""

    def continue_draft(self):
        if not self.is_draft or not self.detail:
            return
        order = self.detail.get("order") or {}
        kit = self.detail.get("kit") or {}
        config = order.get("configuration") or {}
        kit_code = config.get("kit_code") or kit.get("code") or ""
        option_tokens = config.get("option_codes") or []
        lines = config.get("lines") or self.detail.get("lines") or []
        self.loading = True
        self.error_text = "Восстанавливаем черновик..."

        def worker():
            try:
                kit_detail = api_client.get_chevron_kit_detail(kit_code)
                quote_payload = api_client.create_chevron_quote(kit_code, option_tokens, lines)
            except Exception as exc:
                msg = f"Ошибка восстановления: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.error_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, kit_detail=kit_detail, quote_payload=quote_payload):
                self.loading = False
                selected_options = self._selected_from_tokens(option_tokens)
                configurator = self.manager.get_screen("chevron_configurator")
                configurator.kit_code = kit_code
                configurator.kit_title = kit.get("title") or kit_detail.get("kit", {}).get("title") or "Комплект"
                configurator.kit_detail = kit_detail
                configurator.selected_options = selected_options
                configurator.price_available = bool(kit_detail.get("kit", {}).get("price_available"))
                configurator._render()

                names = self.manager.get_screen("chevron_names_draft")
                names.set_config(
                    configurator.kit_title,
                    kit_code,
                    kit_detail,
                    selected_options,
                    configurator.price_available,
                    configurator.price_text,
                )
                names.name_lines = [
                    {
                        "text_value": line.get("text_value") or "",
                        "quantity": int(line.get("quantity") or 1),
                    }
                    for line in lines
                ]
                names._render_lines()

                confirm = self.manager.get_screen("chevron_quote_confirm")
                confirm.set_quote(
                    configurator.kit_title,
                    kit_code,
                    names.summary_text,
                    option_tokens,
                    names.name_lines,
                    quote_payload,
                )
                order = self.detail.get("order") or {}
                confirm.saved = True
                confirm.save_button_text = "Черновик сохранён"
                confirm.draft_status_text = f"Черновик восстановлен. Номер заказа: {order.get('order_number') or ''}"
                self.manager.current = "chevron_quote_confirm"

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _selected_from_tokens(self, tokens):
        selected = {}
        for token in tokens or []:
            if ":" not in str(token):
                continue
            group_code, option_code = str(token).split(":", 1)
            current = selected.get(group_code)
            if current is None:
                selected[group_code] = option_code
            elif isinstance(current, list):
                current.append(option_code)
            else:
                selected[group_code] = [current, option_code]
        return selected

    def goto_orders(self):
        self.manager.current = "chevron_orders"


class ChevronOrderScreen(Screen):
    status_text = StringProperty("")
    active_tab = StringProperty("kits")

    def on_pre_enter(self, *args):
        self.active_tab = "kits"
        self.load_kits()

    def load_kits(self):
        self.status_text = "Загружаем комплекты..."
        self.ids.chevron_kits_list.data = []

        def worker():
            try:
                data = api_client.get_chevron_kits()
            except Exception as exc:
                msg = f"Ошибка комплектов: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                kits = data.get("kits") or []
                self.ids.chevron_kits_list.data = [
                    {
                        "title": kit.get("title") or "",
                        "subtitle": kit.get("subtitle") or "",
                        "icon_text": kit.get("icon") or "",
                        "action": "kit",
                        "payload": kit,
                    }
                    for kit in kits
                ]
                self.status_text = "" if kits else "Комплекты не найдены на сервере."

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def select_tab(self, tab_code):
        self.active_tab = tab_code
        if tab_code == "kits":
            self.load_kits()
            return
        self.ids.chevron_kits_list.data = []
        self.status_text = "Эта вкладка будет подключена после ветки комплектов."

    def handle_nav_action(self, action, payload):
        if action != "kit":
            return
        configurator = self.manager.get_screen("chevron_configurator")
        configurator.open_kit(payload.get("code") or "", payload.get("title") or "Комплект")
        self.manager.current = "chevron_configurator"

    def goto_voentorg(self):
        self.manager.current = "voentorg"


class ChevronKitDetailScreen(Screen):
    kit_code = StringProperty("")
    kit_title = StringProperty("Комплект")
    status_text = StringProperty("")

    def on_pre_enter(self, *args):
        self.load_kit()

    def load_kit(self):
        if not self.kit_code:
            self.status_text = "Комплект не выбран"
            return
        self.status_text = "Загружаем состав комплекта..."
        self.ids.kit_items_list.data = []

        def worker():
            try:
                kit = api_client.get_chevron_kit(self.kit_code)
            except Exception as exc:
                msg = f"Ошибка комплекта: {exc}"

                def ui_fail(dt, msg=msg):
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, kit=kit):
                self.kit_title = kit.get("title") or self.kit_title
                items = kit.get("items") or []
                self.ids.kit_items_list.data = [
                    {
                        "title": item.get("title") or "",
                        "subtitle": f"{item.get('unit') or 'шт'}",
                        "icon_text": str(index).zfill(2),
                        "action": "",
                        "payload": item,
                    }
                    for index, item in enumerate(items, start=1)
                ]
                self.status_text = "" if items else "Состав комплекта не найден на сервере."

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def choose_other(self):
        self.manager.current = "chevron_order"

    def next_step(self):
        self.status_text = "Конфигуратор будет во втором коммите."

    def goto_chevrons(self):
        self.manager.current = "chevron_order"


class ChevronConfiguratorScreen(Screen):
    kit_code = StringProperty("")
    kit_title = StringProperty("Комплект")
    status_text = StringProperty("")
    price_text = StringProperty("Стоимость пока не назначена")
    next_button_text = StringProperty("Далее")
    loading = BooleanProperty(False)
    kit_detail = ObjectProperty({})
    selected_options = ObjectProperty({})
    price_available = BooleanProperty(False)
    preliminary_price_rub = NumericProperty(0)
    preliminary_price_st = NumericProperty(0)

    def open_kit(self, kit_code, kit_title):
        if self.kit_code != kit_code:
            self.kit_detail = {}
            self.selected_options = {}
            self.ids.config_items.data = []
            self.ids.config_options.data = []
        self.kit_code = kit_code
        self.kit_title = kit_title

    def on_pre_enter(self, *args):
        if self.kit_detail and self.kit_detail.get("kit", {}).get("code") == self.kit_code:
            self._render()
            return
        self.load_detail()

    def load_detail(self):
        if not self.kit_code:
            self.status_text = "Комплект не выбран"
            return
        self.loading = True
        self.status_text = "Загружаем конфигуратор..."
        self.ids.config_items.data = []
        self.ids.config_options.data = []

        def worker():
            try:
                data = api_client.get_chevron_kit_detail(self.kit_code)
            except Exception as exc:
                msg = f"Ошибка конфигуратора: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.loading = False
                self.kit_detail = data
                kit = data.get("kit") or {}
                self.kit_title = kit.get("title") or self.kit_title
                self.price_available = bool(kit.get("price_available"))
                self._ensure_selection_state()
                self._render()

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _ensure_selection_state(self):
        if self.selected_options:
            return
        self.selected_options = {}

    def _render(self):
        data = self.kit_detail or {}
        self._render_items(data.get("items") or [])
        self._render_options(data.get("option_groups") or [])
        self._recalculate_price()
        if not self.status_text.startswith("Ошибка"):
            self.status_text = "" if not self.loading else "Загружаем конфигуратор..."

    def _render_items(self, items):
        self.ids.config_items.data = [
            {
                "title": item.get("title") or "",
                "meta": self._item_meta(item),
                "image_url": item.get("image_url") or "",
                "placeholder": "ШЕВРОН",
            }
            for item in items
        ]

    def _item_meta(self, item):
        qty = item.get("quantity") or "1"
        unit = item.get("unit") or "шт"
        required = "обязательная" if item.get("is_required") else "дополнительная"
        return f"{qty} {unit} · {required}"

    def _render_options(self, groups):
        rows = []
        for group in groups:
            options = [
                option for option in (group.get("options") or [])
                if self._option_visible(option)
            ]
            if not options:
                continue
            rows.append({
                "group_code": group.get("code") or "",
                "option_code": "",
                "title": group.get("title") or "",
                "mark": "обязательно" if group.get("is_required") else "",
                "price_text": "",
                "selection_type": "header",
                "selected": False,
                "option_disabled": True,
            })
            for option in options:
                group_code = group.get("code") or ""
                option_code = option.get("code") or ""
                rows.append({
                    "group_code": group_code,
                    "option_code": option_code,
                    "title": option.get("title") or "",
                    "mark": self._option_mark(group.get("selection_type"), group_code, option_code),
                    "price_text": self._option_price_text(option),
                    "selection_type": group.get("selection_type") or "single",
                    "selected": self._is_selected(group_code, option_code),
                    "option_disabled": self._option_disabled(option),
                })
        self.ids.config_options.data = rows

    def _option_visible(self, option):
        visible_if = option.get("visible_if")
        if not visible_if:
            return True
        if not isinstance(visible_if, dict):
            return True
        return self._conditions_match(visible_if)

    def _option_disabled(self, option):
        disabled_if = option.get("disabled_if")
        conflicts = option.get("conflicts_with") or []
        if disabled_if and isinstance(disabled_if, dict) and self._conditions_match(disabled_if):
            return True
        if isinstance(conflicts, list):
            selected_codes = self._selected_codes()
            return any(code in selected_codes for code in conflicts)
        return False

    def _conditions_match(self, conditions):
        selected_codes = self._selected_codes()
        for _, expected in conditions.items():
            if isinstance(expected, list):
                if not any(code in selected_codes for code in expected):
                    return False
            elif expected not in selected_codes:
                return False
        return True

    def _selected_codes(self):
        codes = set()
        for selected in (self.selected_options or {}).values():
            if isinstance(selected, list):
                codes.update(selected)
            elif selected:
                codes.add(selected)
        return codes

    def _is_selected(self, group_code, option_code):
        selected = (self.selected_options or {}).get(group_code)
        if isinstance(selected, list):
            return option_code in selected
        return selected == option_code

    def _option_mark(self, selection_type, group_code, option_code):
        selected = self._is_selected(group_code, option_code)
        if selection_type == "multiple":
            return "✓" if selected else ""
        return "●" if selected else "○"

    def _option_price_text(self, option):
        if option.get("price_available"):
            rub = option.get("price_rub")
            st = option.get("price_st")
            parts = []
            if rub is not None:
                parts.append(f"{rub} ₽")
            if st is not None:
                parts.append(f"{st} ST")
            return " / ".join(parts)
        return "цена не назначена"

    def toggle_option(self, group_code, option_code):
        groups = self.kit_detail.get("option_groups") or []
        group = next((g for g in groups if g.get("code") == group_code), None)
        if not group:
            return
        selected = dict(self.selected_options or {})
        if group.get("selection_type") == "multiple":
            current = list(selected.get(group_code) or [])
            if option_code in current:
                current.remove(option_code)
            else:
                current.append(option_code)
            selected[group_code] = current
        else:
            selected[group_code] = option_code
        self.selected_options = selected
        self._render()

    def _recalculate_price(self):
        kit = (self.kit_detail or {}).get("kit") or {}
        if not kit.get("price_available"):
            self.price_available = False
            self.price_text = "Стоимость пока не назначена"
            return
        rub = kit.get("base_price_rub")
        st = kit.get("base_price_st")
        label = kit.get("pricing_label") or ""
        self.price_text = f"{label}: базовая цена {rub} ₽ / {st} ST"

    def validate_required(self):
        missing = []
        for group in self.kit_detail.get("option_groups") or []:
            if not group.get("is_required"):
                continue
            code = group.get("code")
            selected = (self.selected_options or {}).get(code)
            if isinstance(selected, list):
                ok = len(selected) > 0
            else:
                ok = bool(selected)
            if not ok:
                missing.append(group.get("title") or code)
        if missing:
            self.status_text = "Выберите: " + ", ".join(missing)
            return False
        return True

    def next_step(self):
        if not self.validate_required():
            return
        names_screen = self.manager.get_screen("chevron_names_draft")
        names_screen.set_config(
            self.kit_title,
            self.kit_code,
            self.kit_detail,
            self.selected_options,
            self.price_available,
            self.price_text,
        )
        self.manager.current = "chevron_names_draft"

    def confirm_choose_other(self):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        content.add_widget(make_inventory_label("Текущая конфигурация будет сброшена. Выбрать другой дизайн?"))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = Button(text="Отмена")
        ok = Button(text="Сбросить")
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup = Popup(title="Выбор дизайна", content=content, size_hint=(0.9, 0.42))
        cancel.bind(on_release=popup.dismiss)

        def do_reset(*_):
            popup.dismiss()
            self.selected_options = {}
            self.kit_detail = {}
            self.manager.current = "chevron_order"

        ok.bind(on_release=do_reset)
        popup.open()

    def goto_chevrons(self):
        self.manager.current = "chevron_order"


class ChevronNamesDraftScreen(Screen):
    kit_title = StringProperty("Комплект")
    kit_code = StringProperty("")
    summary_text = StringProperty("")
    status_text = StringProperty("")
    input_text = StringProperty("")
    price_text = StringProperty("Стоимость пока не назначена")
    price_available = BooleanProperty(False)
    loading = BooleanProperty(False)
    kit_detail = ObjectProperty({})
    selected_options = ObjectProperty({})
    name_lines = ListProperty([])

    def set_config(self, kit_title, kit_code, kit_detail, selected_options, price_available, price_text):
        old_key = (self.kit_code, self._selected_codes())
        self.kit_title = kit_title
        self.kit_code = kit_code
        self.kit_detail = kit_detail or {}
        self.selected_options = selected_options or {}
        self.price_available = bool(price_available)
        self.price_text = price_text or "Стоимость пока не назначена"
        new_key = (self.kit_code, self._selected_codes())
        if old_key != new_key:
            self.name_lines = []
        self._render_summary()
        self._render_lines()
        self.status_text = "" if self.price_available else "Оформление временно недоступно: стоимость пока не назначена."

    def _selected_codes(self):
        codes = []
        for value in (self.selected_options or {}).values():
            if isinstance(value, list):
                codes.extend(str(item) for item in value if item)
            elif value:
                codes.append(str(value))
        return tuple(sorted(codes))

    def _render_summary(self):
        lines = [f"Комплект: {self.kit_title}", "Параметры:"]
        groups = (self.kit_detail or {}).get("option_groups") or []
        for group in groups:
            selected = (self.selected_options or {}).get(group.get("code"))
            selected_codes = selected if isinstance(selected, list) else ([selected] if selected else [])
            if not selected_codes:
                continue
            titles = []
            for option in group.get("options") or []:
                if option.get("code") in selected_codes:
                    titles.append(option.get("title") or option.get("code"))
            if titles:
                lines.append(f"{group.get('title')}: {', '.join(titles)}")
        lines.append(self.price_text)
        self.summary_text = "\n".join(lines)

    def _render_lines(self):
        self.ids.names_lines.data = [
            {
                "line_index": index,
                "text_value": line.get("text_value") or "",
                "quantity": int(line.get("quantity") or 1),
            }
            for index, line in enumerate(self.name_lines)
        ]

    def add_line(self, confirmed_duplicate=False):
        value = (self.ids.name_input.text or "").strip()
        if not value:
            self.status_text = "Введите фамилию или позывной."
            return
        duplicate = any((line.get("text_value") or "").strip().lower() == value.lower() for line in self.name_lines)
        if duplicate and not confirmed_duplicate:
            self._confirm_duplicate(value)
            return
        lines = list(self.name_lines)
        lines.append({"text_value": value, "quantity": 1})
        self.name_lines = lines
        self.ids.name_input.text = ""
        self.status_text = "" if self.price_available else "Оформление временно недоступно: стоимость пока не назначена."
        self._render_lines()

    def _confirm_duplicate(self, value):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        content.add_widget(make_inventory_label(f"Строка «{value}» уже есть. Добавить дубль?"))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = Button(text="Отмена")
        ok = Button(text="Добавить")
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup = Popup(title="Дубликат", content=content, size_hint=(0.9, 0.42))
        cancel.bind(on_release=popup.dismiss)

        def do_add(*_):
            popup.dismiss()
            self.add_line(confirmed_duplicate=True)

        ok.bind(on_release=do_add)
        popup.open()

    def edit_line(self, index):
        if index < 0 or index >= len(self.name_lines):
            return
        current = self.name_lines[index].get("text_value") or ""
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        field = TextInput(text=current, multiline=False, size_hint_y=None, height=dp(46))
        content.add_widget(field)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        cancel = Button(text="Отмена")
        ok = Button(text="Сохранить")
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup = Popup(title="Редактировать строку", content=content, size_hint=(0.9, 0.38))
        cancel.bind(on_release=popup.dismiss)

        def do_save(*_):
            value = (field.text or "").strip()
            if not value:
                self.status_text = "Пустую строку сохранить нельзя."
                return
            lines = list(self.name_lines)
            lines[index] = {"text_value": value, "quantity": max(1, int(lines[index].get("quantity") or 1))}
            self.name_lines = lines
            self._render_lines()
            popup.dismiss()

        ok.bind(on_release=do_save)
        popup.open()

    def remove_line(self, index):
        if index < 0 or index >= len(self.name_lines):
            return
        lines = list(self.name_lines)
        lines.pop(index)
        self.name_lines = lines
        self._render_lines()

    def change_quantity(self, index, delta):
        if index < 0 or index >= len(self.name_lines):
            return
        lines = list(self.name_lines)
        current = max(1, int(lines[index].get("quantity") or 1))
        lines[index] = {
            "text_value": lines[index].get("text_value") or "",
            "quantity": max(1, current + int(delta)),
        }
        self.name_lines = lines
        self._render_lines()

    def continue_step(self):
        if not self.name_lines:
            self.status_text = "Добавьте хотя бы одну фамилию или позывной."
            return
        lines = [
            {
                "text_value": (line.get("text_value") or "").strip(),
                "quantity": max(1, int(line.get("quantity") or 1)),
            }
            for line in self.name_lines
            if (line.get("text_value") or "").strip()
        ]
        if len(lines) != len(self.name_lines):
            self.status_text = "Удалите или заполните пустые строки."
            return
        self.loading = True
        self.status_text = "Проверяем стоимость..."
        option_codes = self._selected_option_tokens()

        def worker():
            try:
                data = api_client.create_chevron_quote(self.kit_code, option_codes, lines)
            except Exception as exc:
                msg = f"Ошибка расчёта: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.loading = False
                confirm = self.manager.get_screen("chevron_quote_confirm")
                confirm.set_quote(
                    self.kit_title,
                    self.kit_code,
                    self.summary_text,
                    option_codes,
                    lines,
                    data,
                )
                self.manager.current = "chevron_quote_confirm"

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _selected_option_tokens(self):
        tokens = []
        for group_code, value in (self.selected_options or {}).items():
            if isinstance(value, list):
                tokens.extend(f"{group_code}:{option_code}" for option_code in value if option_code)
            elif value:
                tokens.append(f"{group_code}:{value}")
        return tokens

    def goto_configurator(self):
        self.manager.current = "chevron_configurator"


class ChevronQuoteConfirmScreen(Screen):
    title_text = StringProperty("Подтверждение")
    summary_text = StringProperty("")
    lines_text = StringProperty("")
    price_text = StringProperty("Стоимость пока не назначена")
    pricing_label = StringProperty("")
    draft_status_text = StringProperty("")
    save_button_text = StringProperty("Сохранить черновик")
    checkout_button_text = StringProperty("Оформить тестовый заказ")
    payment_method = StringProperty("RUB")
    saving = BooleanProperty(False)
    checking_out = BooleanProperty(False)
    saved = BooleanProperty(False)
    kit_code = StringProperty("")
    option_codes = ListProperty([])
    order_lines = ListProperty([])
    idempotency_key = StringProperty("")
    checkout_idempotency_key = StringProperty("")
    quote = ObjectProperty({})

    def set_quote(self, kit_title, kit_code, summary_text, option_codes, lines, quote_payload):
        quote = (quote_payload or {}).get("quote") or {}
        self.title_text = f"Подтверждение: {kit_title}"
        self.kit_code = kit_code
        self.option_codes = list(option_codes or [])
        self.order_lines = list(lines or [])
        self.quote = quote
        self.summary_text = summary_text or ""
        self.lines_text = "\n".join(
            self._line_price_text(line) for line in quote.get("lines") or lines
        )
        self.idempotency_key = uuid.uuid4().hex
        self.checkout_idempotency_key = uuid.uuid4().hex
        self.saved = False
        self.saving = False
        self.checking_out = False
        self.save_button_text = "Сохранить черновик"
        self.checkout_button_text = "Оформить тестовый заказ"
        self.pricing_label = quote.get("pricing_label") or ""
        self.draft_status_text = ""
        if quote.get("price_available"):
            rub = quote.get("total_price_rub")
            st = quote.get("total_price_st")
            parts = []
            if rub is not None:
                parts.append(f"{rub} ₽")
            if st is not None:
                parts.append(f"{st} ST")
            self.price_text = "Стоимость: " + " / ".join(parts)
        else:
            self.price_text = "Стоимость пока не назначена"

    def _line_price_text(self, line):
        base = f"{line.get('text_value')} × {line.get('quantity')}"
        rub = line.get("line_total_rub")
        st = line.get("line_total_st")
        if rub is not None and st is not None:
            return f"{base} — {rub} ₽ / {st} ST"
        return base

    def set_payment_method(self, method):
        self.payment_method = method

    def goto_names(self):
        self.manager.current = "chevron_names_draft"

    def save_draft(self):
        if self.saving or self.saved:
            return
        self.saving = True
        self.save_button_text = "Сохраняем..."
        self.draft_status_text = ""

        def worker():
            try:
                data = api_client.create_chevron_draft_order(
                    self.kit_code,
                    list(self.option_codes),
                    list(self.order_lines),
                    self.idempotency_key,
                )
            except Exception as exc:
                msg = f"Не удалось сохранить черновик: {exc}"

                def ui_fail(dt, msg=msg):
                    self.saving = False
                    self.save_button_text = "Повторить"
                    self.draft_status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                order = data.get("order") or {}
                number = order.get("order_number") or "без номера"
                self.saving = False
                self.saved = True
                self.save_button_text = "Черновик сохранён"
                self.draft_status_text = f"Черновик сохранён. Номер заказа: {number}"

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def create_test_order(self):
        if self.checking_out:
            return
        if (self.quote or {}).get("pricing_mode") != "TEST":
            self.draft_status_text = "Тестовое оформление доступно только в TEST режиме."
            return
        if not (self.quote or {}).get("price_available"):
            self.draft_status_text = "Цены не назначены."
            return
        self.checking_out = True
        self.checkout_button_text = "Оформляем..."
        self.draft_status_text = ""

        def worker():
            try:
                data = api_client.create_chevron_test_order(
                    self.kit_code,
                    list(self.option_codes),
                    list(self.order_lines),
                    self.checkout_idempotency_key,
                    self.payment_method,
                )
            except Exception as exc:
                msg = f"Не удалось оформить тестовый заказ: {exc}"

                def ui_fail(dt, msg=msg):
                    self.checking_out = False
                    self.checkout_button_text = "Повторить оформление"
                    self.draft_status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                order = data.get("order") or {}
                number = order.get("order_number") or "без номера"
                self.checking_out = False
                self.checkout_button_text = "Тестовый заказ создан"
                self.draft_status_text = f"Тестовый заказ создан. Средства не списаны. Номер: {number}"

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()


class ChevronAdminPricingScreen(Screen):
    status_text = StringProperty("")
    loading = BooleanProperty(False)
    saving = BooleanProperty(False)
    pricing = ObjectProperty({})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.kit_fields = {}
        self.option_fields = {}
        self.settings_fields = {}

    def on_pre_enter(self, *args):
        self.load_pricing()

    def load_pricing(self):
        self.loading = True
        self.status_text = "Загружаем настройки..."
        self.ids.pricing_box.clear_widgets()

        def worker():
            try:
                data = api_client.get_chevron_admin_pricing()
            except Exception as exc:
                msg = f"Ошибка настроек: {exc}"

                def ui_fail(dt, msg=msg):
                    self.loading = False
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.loading = False
                self.pricing = data.get("pricing") or {}
                self._render()

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _render(self):
        box = self.ids.pricing_box
        box.clear_widgets()
        self.kit_fields = {}
        self.option_fields = {}
        self.settings_fields = {}
        pricing = self.pricing or {}
        settings = pricing.get("settings") or {}

        box.add_widget(make_inventory_label("Тестовые цены"))
        box.add_widget(self._settings_card(settings))

        box.add_widget(make_inventory_label("Цены комплектов"))
        for kit in pricing.get("kits") or []:
            box.add_widget(self._kit_card(kit))

        box.add_widget(make_inventory_label("Цены опций"))
        for group in pricing.get("option_groups") or []:
            box.add_widget(make_inventory_label(group.get("title") or group.get("code") or "Группа"))
            for option in group.get("options") or []:
                box.add_widget(self._option_card(group, option))

        missing = pricing.get("missing_fields") or []
        self.status_text = (
            "Настройки заполнены. Оформление включено."
            if pricing.get("ordering_enabled")
            else f"Оформление выключено. Не заполнено: {len(missing)}"
        )

    def _settings_card(self, settings):
        card = self._card(dp(268))
        card.add_widget(self._label("Режим и общие настройки", bold=True))
        mode = Spinner(
            text=settings.get("pricing_mode") or "TEST",
            values=("TEST", "PRODUCTION"),
            size_hint_y=None,
            height=dp(44),
        )
        rate = self._input(settings.get("st_rate_rub"), "Курс 1 СТ в рублях")
        instruction = self._input(settings.get("rub_payment_instruction"), "Инструкция оплаты рублями", multiline=True, height=dp(76))
        ordering = Spinner(
            text="Включено" if settings.get("ordering_enabled") else "Выключено",
            values=("Выключено", "Включено"),
            size_hint_y=None,
            height=dp(44),
        )
        self.settings_fields = {
            "pricing_mode": mode,
            "st_rate_rub": rate,
            "rub_payment_instruction": instruction,
            "ordering_enabled": ordering,
        }
        card.add_widget(mode)
        card.add_widget(rate)
        card.add_widget(instruction)
        card.add_widget(ordering)
        return card

    def _kit_card(self, kit):
        card = self._card(dp(208))
        card.add_widget(self._label(kit.get("title") or kit.get("code") or "Комплект", bold=True))
        rub = self._input(kit.get("price_rub"), "Цена ₽")
        st = self._input(kit.get("price_st"), "Цена СТ")
        unit = Spinner(
            text=kit.get("pricing_unit") or "PER_SET",
            values=("PER_SET", "PER_LINE", "PER_ITEM"),
            size_hint_y=None,
            height=dp(44),
        )
        self.kit_fields[kit.get("code")] = {"price_rub": rub, "price_st": st, "pricing_unit": unit}
        card.add_widget(rub)
        card.add_widget(st)
        card.add_widget(unit)
        return card

    def _option_card(self, group, option):
        card = self._card(dp(154))
        card.add_widget(self._label(option.get("title") or option.get("code") or "Опция", bold=True))
        rub = self._input(option.get("price_rub"), "Доплата ₽")
        st = self._input(option.get("price_st"), "Доплата СТ")
        key = (group.get("code"), option.get("code"))
        self.option_fields[key] = {"price_rub": rub, "price_st": st}
        card.add_widget(rub)
        card.add_widget(st)
        return card

    def _card(self, height):
        card = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8), size_hint_y=None, height=height)
        with card.canvas.before:
            Color(1, 1, 1, 1)
            card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
            Color(0.86, 0.86, 0.86, 1)
            card._border = Line(rounded_rectangle=(card.x, card.y, card.width, card.height, dp(8)), width=1)

        def sync(instance, *_):
            instance._bg.pos = instance.pos
            instance._bg.size = instance.size
            instance._border.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, dp(8))

        card.bind(pos=sync, size=sync)
        return card

    def _label(self, text, bold=False):
        lbl = Label(
            text=str(text),
            bold=bold,
            color=(0.05, 0.05, 0.05, 1),
            font_size="15sp",
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(24),
        )
        lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
        return lbl

    def _input(self, value, hint, multiline=False, height=None):
        field = TextInput(
            text="" if value is None else str(value),
            hint_text=hint,
            multiline=multiline,
            size_hint_y=None,
            height=height or dp(42),
            font_size="14sp",
            padding=(dp(10), dp(9)),
        )
        return field

    def save_pricing(self):
        if self.saving:
            return
        settings = {
            "pricing_mode": self.settings_fields["pricing_mode"].text,
            "st_rate_rub": self._nullable_text(self.settings_fields["st_rate_rub"]),
            "rub_payment_instruction": self._nullable_text(self.settings_fields["rub_payment_instruction"]),
            "ordering_enabled": self.settings_fields["ordering_enabled"].text == "Включено",
        }
        if settings["pricing_mode"] == "PRODUCTION":
            settings["confirm_production"] = True
        kit_prices = []
        for kit_code, fields in self.kit_fields.items():
            kit_prices.append({
                "kit_code": kit_code,
                "price_rub": self._nullable_text(fields["price_rub"]),
                "price_st": self._nullable_text(fields["price_st"]),
                "pricing_unit": fields["pricing_unit"].text,
            })
        options = []
        for (group_code, option_code), fields in self.option_fields.items():
            options.append({
                "group_code": group_code,
                "code": option_code,
                "price_rub": self._nullable_text(fields["price_rub"]),
                "price_st": self._nullable_text(fields["price_st"]),
            })

        self.saving = True
        self.status_text = "Сохраняем..."

        def worker():
            try:
                data = api_client.update_chevron_admin_pricing(settings, kit_prices, options)
            except Exception as exc:
                msg = f"Ошибка сохранения: {exc}"

                def ui_fail(dt, msg=msg):
                    self.saving = False
                    self.status_text = msg

                Clock.schedule_once(ui_fail)
                return

            def ui_ok(dt, data=data):
                self.saving = False
                self.pricing = data.get("pricing") or {}
                self._render()
                self.status_text = "Настройки сохранены."

            Clock.schedule_once(ui_ok)

        threading.Thread(target=worker, daemon=True).start()

    def _nullable_text(self, field):
        value = (field.text or "").strip()
        return None if value == "" else value

    def goto_employee(self):
        self.manager.current = "employee_panel"


class EmployeePanelScreen(Screen):
    def on_pre_enter(self, *args):
        app = App.get_running_app()
        user = app.current_user or {}
        is_admin = int(user.get("access") or 0) == 1
        self.ids.btn_admin_pricing.disabled = not is_admin
        self.ids.btn_admin_pricing.opacity = 1 if is_admin else 0
        self.ids.btn_admin_pricing.height = dp(52) if is_admin else 0
        fill_cards(
            self.ids.employee_cards,
            [
                "Вышивальщик",
                "Вырезальщик / комплектовальщик",
                "Доставщик",
            ],
        )

    def goto_admin_pricing(self):
        self.manager.current = "chevron_admin_pricing"

    def goto_home(self):
        self.manager.current = "user_home"


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
        sm.add_widget(FinanceAccountScreen(name="finance_account"))
        sm.add_widget(VoentorgScreen(name="voentorg"))
        sm.add_widget(ChevronOrdersScreen(name="chevron_orders"))
        sm.add_widget(ChevronOrderDetailScreen(name="chevron_order_detail"))
        sm.add_widget(ChevronOrderScreen(name="chevron_order"))
        sm.add_widget(ChevronKitDetailScreen(name="chevron_kit_detail"))
        sm.add_widget(ChevronConfiguratorScreen(name="chevron_configurator"))
        sm.add_widget(ChevronNamesDraftScreen(name="chevron_names_draft"))
        sm.add_widget(ChevronQuoteConfirmScreen(name="chevron_quote_confirm"))
        sm.add_widget(ChevronAdminPricingScreen(name="chevron_admin_pricing"))
        sm.add_widget(EmployeePanelScreen(name="employee_panel"))
        sm.add_widget(TransferListScreen(name="transfers"))
        sm.add_widget(TransferCreateScreen(name="transfer_create"))
        sm.add_widget(FormsMenuScreen(name="forms_menu"))
        sm.add_widget(FormViewScreen(name="form_view"))
        return sm


if __name__ == "__main__":
    SixnerInventoryApp().run()
