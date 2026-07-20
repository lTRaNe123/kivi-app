# api_client.py
import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import requests


class ApiError(Exception):
    """Исключение для ошибок API."""
    pass


@dataclass
class ApiConfig:
    base_url: str
    timeout: int = 10  # секунд


class ApiClient:
    """
    Обёртка над HTTP API.

    Ожидаемые PHP-скрипты:
      /api/login.php
      /api/book_get_assignments.php
      /api/book_confirm_assignment.php   (если понадобится)
      /api/transfer_list.php
      /api/transfer_confirm.php
      /api/transfer_create.php
      /api/users.php
      /api/form_view.php
      /api/finance_profile.php
      /api/finance_transfer.php
      /api/finance_withdraw.php
      /api/voentorg_menu.php
      /api/chevron_kits.php
      /api/chevron_kit_detail.php
      /api/chevron_quote.php
      /api/chevron_order_create.php
      /api/chevron_orders.php
      /api/chevron_order_detail.php
      /api/chevron_admin_pricing_get.php
      /api/chevron_admin_pricing_update.php
      /api/employee_profile.php
      /api/employee_orders.php
      /api/employee_order_detail.php
      /api/employee_order_claim.php
      /api/employee_order_complete.php
    """

    def __init__(self, base_url: str):
        # base_url = "http://85.159.231.68"
        self.cfg = ApiConfig(base_url=base_url.rstrip("/"))
        self.session = requests.Session()
        self.user_id: Optional[int] = None
        self.api_token: Optional[str] = None

    # ----- служебные методы -----

    def _url(self, script: str) -> str:
        """
        Собрать полный URL вида http://host/api/script.php
        """
        script = script.lstrip("/")
        return f"{self.cfg.base_url}/api/{script}"

    def _request_json(
        self,
        method: str,
        script: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Выполнить запрос и вернуть JSON.
        Если success=false или формат неправильный — бросаем ApiError.
        """
        url = self._url(script)
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        try:
            if method.upper() == "GET":
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.cfg.timeout,
                )
            else:
                resp = self.session.post(
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.cfg.timeout,
                )
        except requests.RequestException as e:
            raise ApiError(f"Сетевая ошибка: {e}") from e

        if resp.status_code != 200:
            raise ApiError(f"HTTP {resp.status_code} при обращении к {script}")

        try:
            payload = resp.json()
        except json.JSONDecodeError as e:
            text = resp.text[:200].replace("\n", " ")
            raise ApiError(f"Неверный JSON от сервера ({script}): {text}") from e

        # стандартный формат: { "success": true/false, "error": "..." }
        if isinstance(payload, dict) and "success" in payload:
            if not payload.get("success"):
                err = payload.get("error") or "Запрос отклонён сервером"
                raise ApiError(str(err))

        return payload

    # ----- публичные методы -----

    def health(self) -> Dict[str, Any]:
        """
        GET /api/health.php

        Проверяет, что мобильное приложение смотрит на тот же сервер,
        где поднят сайт и PHP API. Не требует авторизации.
        """
        return self._request_json("GET", "health.php")

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        POST /api/login.php
        """
        data = {
            "username": username,
            "password": password,
        }
        payload = self._request_json("POST", "login.php", data=data)
        token = payload.get("token")
        if not token:
            raise ApiError("Успешный вход, но сервер не вернул токен авторизации")
        self.api_token = str(token)

        user = payload.get("user")
        if not user or not isinstance(user, dict):
            # возможно, сервер кладёт поля пользователя сразу в корень
            user = payload

        # пробуем вытащить user_id из разных возможных полей
        user_id = (
            payload.get("user_id")
            or user.get("user_id")
            or user.get("uid")
            or user.get("id")
        )

        try:
            self.user_id = int(user_id)
        except (TypeError, ValueError):
            raise ApiError("Успешный вход, но сервер не вернул корректный user_id")

        return user

    def get_assignments(self) -> List[Dict[str, Any]]:
        """
        GET /api/book_get_assignments.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "book_get_assignments.php")

        assignments = (
            payload.get("assignments")
            or payload.get("docs")
            or []
        )
        if not isinstance(assignments, list):
            raise ApiError("Некорректный формат списка накладных")
        return assignments

    def get_transfer_lists(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        GET /api/transfer_list.php
        Ожидается:
        { "success": true, "incoming": [...], "outgoing": [...] }
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "transfer_list.php")

        incoming = payload.get("incoming") or []
        outgoing = payload.get("outgoing") or []
        if not isinstance(incoming, list) or not isinstance(outgoing, list):
            raise ApiError("Некорректный формат списка передач")

        return incoming, outgoing

    def confirm_transfer(self, tid: int, action: str) -> None:
        """
        POST /api/transfer_confirm.php
        data: { tid: ..., action: "accept" | "reject" }
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        data = {
            "tid": tid,
            "action": action,
        }
        self._request_json("POST", "transfer_confirm.php", data=data)

    def create_transfer(
        self,
        to_uid: int,
        comment: str,
        items: List[Dict[str, Any]],
    ) -> int:
        """
        POST /api/transfer_create.php
        data:
          to_uid  – получатель
          comment – комментарий
          items   – JSON-строка с массивом [{name, qty, unit}, ...]
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        data = {
            "to_uid": to_uid,
            "comment": comment,
            "items": json.dumps(items, ensure_ascii=False),
        }
        payload = self._request_json("POST", "transfer_create.php", data=data)

        tid = payload.get("tid")
        try:
            return int(tid)
        except (TypeError, ValueError):
            raise ApiError("Сервер не вернул номер созданной передачи (tid)")

    def get_users(self) -> List[Dict[str, Any]]:
        """
        GET /api/users.php
        Ожидается: { "success": true, "users": [ ... ] }
        """
        if not self.user_id:
            # формально можно и без этого, но лучше проверять
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "users.php")
        users = payload.get("users") or []
        if not isinstance(users, list):
            raise ApiError("Некорректный формат списка пользователей")
        return users

    def get_finance_profile(
        self,
        query: str = "",
        page: int = 1,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        GET /api/finance_profile.php

        Возвращает профиль, баланс и структурированную таблицу:
        { profile, table: { columns, rows, links, actions, pagination } }
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        params = {
            "page": page,
            "limit": limit,
        }
        if query:
            params["q"] = query

        payload = self._request_json("GET", "finance_profile.php", params=params)
        table = payload.get("table") or {}
        if not isinstance(table.get("columns") or [], list):
            raise ApiError("API ЛК не вернул columns")
        if not isinstance(table.get("rows") or [], list):
            raise ApiError("API ЛК не вернул rows")
        return payload

    def create_finance_transfer(
        self,
        to_uid: int,
        amount: float,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        POST /api/finance_transfer.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        data = {
            "to_uid": to_uid,
            "amount": amount,
            "comment": comment,
            "idempotency_key": uuid.uuid4().hex,
        }
        return self._request_json("POST", "finance_transfer.php", data=data)

    def create_finance_withdraw(
        self,
        amount: float,
        comment: str = "",
    ) -> Dict[str, Any]:
        """
        POST /api/finance_withdraw.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        data = {
            "amount": amount,
            "details": comment,
            "idempotency_key": uuid.uuid4().hex,
        }
        return self._request_json("POST", "finance_withdraw.php", data=data)

    def get_form(self, code: str) -> Dict[str, Any]:
        """
        GET /api/form_view.php?code=...

        Авторизация идёт через bearer-токен, а не через user_id.
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        params = {
            "code": code,
        }
        payload = self._request_json("GET", "form_view.php", params=params)
        if not isinstance(payload, dict):
            raise ApiError("Некорректный ответ form_view.php")
        return payload

    def get_voentorg_menu(self) -> List[Dict[str, Any]]:
        """
        GET /api/voentorg_menu.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "voentorg_menu.php")
        sections = payload.get("sections") or []
        if not isinstance(sections, list):
            raise ApiError("API Военторга не вернул sections")
        return sections

    def get_chevron_kits(self) -> Dict[str, Any]:
        """
        GET /api/chevron_kits.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "chevron_kits.php")
        if not isinstance(payload.get("kits") or [], list):
            raise ApiError("API шевронов не вернул kits")
        return payload

    def get_chevron_kit(self, kit_code: str) -> Dict[str, Any]:
        """
        GET /api/chevron_kits.php?kit=...
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "GET",
            "chevron_kits.php",
            params={"kit": kit_code},
        )
        kit = payload.get("kit") or {}
        if not isinstance(kit, dict):
            raise ApiError("API шевронов не вернул kit")
        return kit

    def get_chevron_kit_detail(self, kit_code: str) -> Dict[str, Any]:
        """
        GET /api/chevron_kit_detail.php?code=...
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "GET",
            "chevron_kit_detail.php",
            params={"code": kit_code},
        )
        if not isinstance(payload.get("kit") or {}, dict):
            raise ApiError("API конфигуратора не вернул kit")
        if not isinstance(payload.get("items") or [], list):
            raise ApiError("API конфигуратора не вернул items")
        if not isinstance(payload.get("option_groups") or [], list):
            raise ApiError("API конфигуратора не вернул option_groups")
        return payload

    def create_chevron_quote(
        self,
        kit_code: str,
        option_codes: List[str],
        lines: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        POST /api/chevron_quote.php
        Сервер пересчитывает стоимость сам, приложение передаёт только выбор.
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "POST",
            "chevron_quote.php",
            data={
                "kit_code": kit_code,
                "option_codes": json.dumps(option_codes, ensure_ascii=False),
                "lines": json.dumps(lines, ensure_ascii=False),
            },
        )
        if not isinstance(payload.get("quote") or {}, dict):
            raise ApiError("API расчёта не вернул quote")
        return payload

    def create_chevron_draft_order(
        self,
        kit_code: str,
        option_codes: List[str],
        lines: List[Dict[str, Any]],
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """
        POST /api/chevron_order_create.php
        Создаёт или возвращает DRAFT-заказ по idempotency_key.
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "POST",
            "chevron_order_create.php",
            data={
                "kit_code": kit_code,
                "option_codes": json.dumps(option_codes, ensure_ascii=False),
                "lines": json.dumps(lines, ensure_ascii=False),
                "status": "DRAFT",
                "idempotency_key": idempotency_key,
            },
        )
        if not isinstance(payload.get("order") or {}, dict):
            raise ApiError("API заказа не вернул order")
        return payload

    def create_chevron_test_order(
        self,
        kit_code: str,
        option_codes: List[str],
        lines: List[Dict[str, Any]],
        idempotency_key: str,
        payment_method: str,
    ) -> Dict[str, Any]:
        """
        POST /api/chevron_order_create.php
        Создаёт тестовый заказ без реального списания средств.
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "POST",
            "chevron_order_create.php",
            data={
                "kit_code": kit_code,
                "option_codes": json.dumps(option_codes, ensure_ascii=False),
                "lines": json.dumps(lines, ensure_ascii=False),
                "status": "TEST_ORDER",
                "payment_method": payment_method,
                "idempotency_key": idempotency_key,
            },
        )
        if not isinstance(payload.get("order") or {}, dict):
            raise ApiError("API заказа не вернул order")
        return payload

    def get_chevron_orders(
        self,
        status: str = "",
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        GET /api/chevron_orders.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        params = {
            "page": page,
            "limit": limit,
        }
        if status:
            params["status"] = status
        payload = self._request_json("GET", "chevron_orders.php", params=params)
        if not isinstance(payload.get("orders") or [], list):
            raise ApiError("API заказов не вернул orders")
        return payload

    def get_chevron_order_detail(self, order_id: int) -> Dict[str, Any]:
        """
        GET /api/chevron_order_detail.php?id=...
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "GET",
            "chevron_order_detail.php",
            params={"id": order_id},
        )
        if not isinstance(payload.get("order") or {}, dict):
            raise ApiError("API заказа не вернул order")
        return payload

    def get_chevron_admin_pricing(self) -> Dict[str, Any]:
        """
        GET /api/chevron_admin_pricing_get.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "chevron_admin_pricing_get.php")
        if not isinstance(payload.get("pricing") or {}, dict):
            raise ApiError("API настроек цен не вернул pricing")
        return payload

    def update_chevron_admin_pricing(
        self,
        settings: Optional[Dict[str, Any]] = None,
        kit_prices: Optional[List[Dict[str, Any]]] = None,
        options: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/chevron_admin_pricing_update.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "POST",
            "chevron_admin_pricing_update.php",
            data={
                "settings": json.dumps(settings or {}, ensure_ascii=False),
                "kit_prices": json.dumps(kit_prices or [], ensure_ascii=False),
                "options": json.dumps(options or [], ensure_ascii=False),
            },
        )
        if not isinstance(payload.get("pricing") or {}, dict):
            raise ApiError("API настроек цен не вернул pricing")
        return payload

    def get_employee_profile(self) -> Dict[str, Any]:
        """
        GET /api/employee_profile.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json("GET", "employee_profile.php")
        if not isinstance(payload.get("employee") or {}, dict):
            raise ApiError("API сотрудника не вернул employee")
        if not isinstance(payload.get("sections") or [], list):
            raise ApiError("API сотрудника не вернул sections")
        return payload

    def get_employee_orders(
        self,
        role: str,
        query: str = "",
        stage: str = "",
        queue: str = "new",
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        GET /api/employee_orders.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        params = {
            "role": role,
            "queue": queue,
            "page": page,
            "limit": limit,
        }
        if query:
            params["q"] = query
        if stage:
            params["stage"] = stage
        payload = self._request_json("GET", "employee_orders.php", params=params)
        if not isinstance(payload.get("orders") or [], list):
            raise ApiError("API очереди не вернул orders")
        return payload

    def get_employee_order_detail(self, order_id: int, role: str) -> Dict[str, Any]:
        """
        GET /api/employee_order_detail.php?id=...&role=...
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        payload = self._request_json(
            "GET",
            "employee_order_detail.php",
            params={"id": order_id, "role": role},
        )
        if not isinstance(payload.get("order") or {}, dict):
            raise ApiError("API рабочего заказа не вернул order")
        return payload

    def claim_employee_order(self, order_id: int, role: str, idempotency_key: str) -> Dict[str, Any]:
        """
        POST /api/employee_order_claim.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        return self._request_json(
            "POST",
            "employee_order_claim.php",
            data={
                "order_id": int(order_id),
                "role": role,
                "idempotency_key": idempotency_key,
            },
        )

    def complete_employee_order(
        self,
        order_id: int,
        role: str,
        comment: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """
        POST /api/employee_order_complete.php
        """
        if not self.user_id:
            raise ApiError("Пользователь не авторизован")

        return self._request_json(
            "POST",
            "employee_order_complete.php",
            data={
                "order_id": int(order_id),
                "role": role,
                "comment": comment or "",
                "idempotency_key": idempotency_key,
            },
        )


# ----- ГЛОБАЛЬНЫЙ КЛИЕНТ ДЛЯ main.py -----

BASE_URL = "http://82.25.61.87:28920"   # сайт + PHP API, без /api в конце
api_client = ApiClient(BASE_URL)
