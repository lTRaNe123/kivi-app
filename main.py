# main.py
import threading
from collections import defaultdict

from kivy.app import App
from kivy.clock import Clock
from kivy.clock import Clock

Clock.max_iteration = 1000

from kivy.lang import Builder
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import (
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
    def on_pre_enter(self, *args):
        fill_cards(
            self.ids.voentorg_cards,
            [
                "Заказ шевронов",
                "Список заказов",
                "Статус заказа",
                "Карточка заказа",
            ],
        )

    def goto_home(self):
        self.manager.current = "user_home"


class EmployeePanelScreen(Screen):
    def on_pre_enter(self, *args):
        fill_cards(
            self.ids.employee_cards,
            [
                "Вышивальщик",
                "Вырезальщик / комплектовальщик",
                "Доставщик",
            ],
        )

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
        sm.add_widget(EmployeePanelScreen(name="employee_panel"))
        sm.add_widget(TransferListScreen(name="transfers"))
        sm.add_widget(TransferCreateScreen(name="transfer_create"))
        sm.add_widget(FormsMenuScreen(name="forms_menu"))
        sm.add_widget(FormViewScreen(name="form_view"))
        return sm


if __name__ == "__main__":
    SixnerInventoryApp().run()
