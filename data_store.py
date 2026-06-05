from dataclasses import dataclass, field
from typing import List, Optional
import random
import string


@dataclass
class User:
    id: int
    full_name: str
    role: str  # ADMIN, OFFICER, USER
    category: str  # СОЛДАТ, НЕ СОЛДАТ
    special_mark: str
    unit: str
    login: str
    password: str


@dataclass
class Item:
    id: int
    name: str
    description: str
    created_by_id: int
    photos: List[str] = field(default_factory=list)


@dataclass
class Assignment:
    id: int
    item: Item
    receiver_id: int
    issued_by_id: int
    status: str  # PENDING, ACCEPTED
    photos: List[str] = field(default_factory=list)


class DataStore:
    def __init__(self):
        self.users: List[User] = []
        self.items: List[Item] = []
        self.assignments: List[Assignment] = []
        self._user_id_seq = 1
        self._item_id_seq = 1
        self._assignment_id_seq = 1
        self.last_created_user: Optional[User] = None

        self._seed_demo_data()

    # --- helpers ---

    @staticmethod
    def _gen_password(length: int = 8) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    def _gen_login(self, full_name: str) -> str:
        base = "user"
        if full_name:
            parts = full_name.split()
            if parts:
                base = parts[0].lower()
        suffix = str(self._user_id_seq).zfill(3)
        login = f"{base}{suffix}"
        existing = {u.login for u in self.users}
        while login in existing:
            suffix = str(random.randint(1, 999)).zfill(3)
            login = f"{base}{suffix}"
        return login

    # --- public API ---

    def create_user(self, full_name: str, unit: str, category: str,
                    special_mark: str, role: str = "USER") -> User:
        login = self._gen_login(full_name)
        password = self._gen_password()
        user = User(
            id=self._user_id_seq,
            full_name=full_name,
            role=role,
            category=category,
            special_mark=special_mark,
            unit=unit,
            login=login,
            password=password,
        )
        self._user_id_seq += 1
        self.users.append(user)
        self.last_created_user = user
        return user

    def check_login(self, login: str, password: str) -> Optional[User]:
        for u in self.users:
            if u.login == login and u.password == password:
                return u
        return None

    def get_user(self, user_id: int) -> Optional[User]:
        for u in self.users:
            if u.id == user_id:
                return u
        return None

    def get_soldiers(self) -> List[User]:
        # Для демо: считаем солдатами всех с role=USER
        return [u for u in self.users if u.role == "USER"]

    def create_item(self, name: str, description: str, created_by_id: int,
                    photos: List[str]) -> Item:
        item = Item(
            id=self._item_id_seq,
            name=name,
            description=description,
            created_by_id=created_by_id,
            photos=list(photos),
        )
        self._item_id_seq += 1
        self.items.append(item)
        return item

    def create_assignment(self, issued_by: User, receiver: User,
                          item_name: str, description: str,
                          photos: List[str]) -> Assignment:
        item = self.create_item(
            name=item_name,
            description=description,
            created_by_id=issued_by.id,
            photos=photos,
        )
        assignment = Assignment(
            id=self._assignment_id_seq,
            item=item,
            receiver_id=receiver.id,
            issued_by_id=issued_by.id,
            status="PENDING",
            photos=list(photos),
        )
        self._assignment_id_seq += 1
        self.assignments.append(assignment)
        return assignment

    def get_pending_for_user(self, user_id: int) -> List[Assignment]:
        return [a for a in self.assignments
                if a.receiver_id == user_id and a.status == "PENDING"]

    def get_inventory_for_user(self, user_id: int) -> List[Assignment]:
        return [a for a in self.assignments
                if a.receiver_id == user_id and a.status == "ACCEPTED"]

    def accept_assignment(self, assignment_id: int, user_id: int) -> bool:
        for a in self.assignments:
            if a.id == assignment_id and a.receiver_id == user_id and a.status == "PENDING":
                a.status = "ACCEPTED"
                return True
        return False

    # --- demo seed ---

    def _seed_demo_data(self):
        # Админ
        admin = User(
            id=self._user_id_seq,
            full_name="Администратор системы",
            role="ADMIN",
            category="НЕ СОЛДАТ",
            special_mark="",
            unit="Штаб",
            login="admin",
            password="admin",
        )
        self._user_id_seq += 1
        self.users.append(admin)

        # Офицер
        officer = User(
            id=self._user_id_seq,
            full_name="Капитан Пупкин",
            role="OFFICER",
            category="НЕ СОЛДАТ",
            special_mark="командир взвода",
            unit="1 взвод",
            login="officer",
            password="officer",
        )
        self._user_id_seq += 1
        self.users.append(officer)

        # Контрактник
        soldier = User(
            id=self._user_id_seq,
            full_name="Контрактник Иванов",
            role="USER",
            category="СОЛДАТ",
            special_mark="водитель",
            unit="1 взвод",
            login="soldier",
            password="soldier",
        )
        self._user_id_seq += 1
        self.users.append(soldier)

        # Пример уже закреплённого имущества
        item = self.create_item(
            name="Лопата МПЛ",
            description="Выдана ранее, состояние хорошее",
            created_by_id=officer.id,
            photos=["lopata1.jpg"],
        )
        assign = Assignment(
            id=self._assignment_id_seq,
            item=item,
            receiver_id=soldier.id,
            issued_by_id=officer.id,
            status="ACCEPTED",
            photos=item.photos,
        )
        self._assignment_id_seq += 1
        self.assignments.append(assign)


store = DataStore()
