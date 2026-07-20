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


# ----- ГЛОБАЛЬНЫЙ КЛИЕНТ ДЛЯ main.py -----

BASE_URL = "http://82.25.61.87:28920"   # сайт + PHP API, без /api в конце
api_client = ApiClient(BASE_URL)
