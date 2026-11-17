# -*- coding: utf-8 -*-
# func/player/ammo_mixin.py - Магазины и shell_ammo (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from config.map_config import WEAPONS, MAGAZINES, AMMO

from utils.logger import get_logger

logger = get_logger()


class AmmoMixin:
    """Магазины (инстансы) + shell_ammo для дробовиков/винтовок."""

    # ==================== МАГАЗИНЫ ====================

    def _has_shell_weapon(self) -> bool:
        weapon_data = WEAPONS.get(self.weapon, {})
        return weapon_data.get('shell_loading', False)

    def _give_starting_magazines(self):
        weapon_data = WEAPONS.get(self.weapon, {})
        weapon_mags = weapon_data.get('magazines', [])

        if not weapon_mags:
            return

        starting_mag_id = weapon_mags[0]
        mag_data = MAGAZINES.get(starting_mag_id, {})
        capacity = mag_data.get('capacity', 0)
        caliber = mag_data.get('caliber', '9x18')

        ammo_type = "оболочечные"
        caliber_data = AMMO.get('calibers', {}).get(caliber, {})
        types = caliber_data.get('types', [])
        if types:
            ammo_type = types[0]

        uid1 = self._generate_magazine_uid()
        uid2 = self._generate_magazine_uid()

        self.magazines.append({
            "uid": uid1,
            "type_id": starting_mag_id,
            "ammo": {ammo_type: capacity},
            "installed": True,
            "weapon": self.weapon
        })

        self.magazines.append({
            "uid": uid2,
            "type_id": starting_mag_id,
            "ammo": {ammo_type: capacity},
            "installed": False,
            "weapon": None
        })

        self.equipped_magazine = uid1
        logger.debug(
            f"{getattr(self, 'name', '?')}: выданы стартовые магазины "
            f"{starting_mag_id} x2 (ammo={ammo_type})"
        )

    def _generate_magazine_uid(self) -> str:
        uid = f"mag_{self.next_magazine_uid}"
        self.next_magazine_uid += 1
        return uid

    def _migrate_old_magazines(self, old_ammo_inventory: dict):
        old_mags = self.magazines
        old_equipped = self.equipped_magazine

        self.magazines = []
        self.equipped_magazine = None
        new_equipped_uid = None

        for mag_type_id in old_mags:
            uid = self._generate_magazine_uid()
            ammo = {}
            if old_ammo_inventory.get(mag_type_id):
                ammo = dict(old_ammo_inventory[mag_type_id])

            self.magazines.append({
                "uid": uid,
                "type_id": mag_type_id,
                "ammo": ammo,
                "installed": False,
                "weapon": None
            })

            if mag_type_id == old_equipped and new_equipped_uid is None:
                new_equipped_uid = uid

        if new_equipped_uid:
            self.equipped_magazine = new_equipped_uid
            for mag in self.magazines:
                if mag["uid"] == new_equipped_uid:
                    mag["installed"] = True
                    mag["weapon"] = self.weapon
                    break

        logger.info(
            f"{getattr(self, 'name', '?')}: миграция старых магазинов, "
            f"перенесено {len(self.magazines)} шт."
        )

    def get_equipped_magazine_obj(self) -> dict:
        if not self.equipped_magazine:
            return None
        for mag in self.magazines:
            if mag["uid"] == self.equipped_magazine:
                return mag
        return None

    def get_magazine_obj(self, uid: str) -> dict:
        for mag in self.magazines:
            if mag["uid"] == uid:
                return mag
        return None

    def get_installed_magazines(self) -> list:
        return [m for m in self.magazines if m.get("installed", False)]

    def get_uninstalled_magazines(self) -> list:
        return [m for m in self.magazines if not m.get("installed", False)]

    def add_magazine_instance(self, type_id: str, ammo: dict = None) -> str:
        uid = self._generate_magazine_uid()
        self.magazines.append({
            "uid": uid,
            "type_id": type_id,
            "ammo": ammo or {},
            "installed": False,
            "weapon": None
        })
        return uid

    def remove_magazine_instance(self, uid: str) -> bool:
        for i, mag in enumerate(self.magazines):
            if mag["uid"] == uid:
                if uid == self.equipped_magazine:
                    self.equipped_magazine = None
                del self.magazines[i]
                return True
        return False

    def install_magazine(self, uid: str) -> bool:
        mag = self.get_magazine_obj(uid)
        if not mag:
            return False
        if mag.get("installed"):
            return False

        if self.equipped_magazine:
            old_mag = self.get_magazine_obj(self.equipped_magazine)
            if old_mag:
                old_mag["installed"] = False
                old_mag["weapon"] = None

        mag["installed"] = True
        mag["weapon"] = self.weapon
        self.equipped_magazine = uid
        return True

    def uninstall_magazine(self) -> str:
        if not self.equipped_magazine:
            return None

        uid = self.equipped_magazine
        mag = self.get_magazine_obj(uid)
        if mag:
            mag["installed"] = False
            mag["weapon"] = None

        self.equipped_magazine = None
        return uid

    def get_magazine_ammo_count(self, uid: str) -> int:
        mag = self.get_magazine_obj(uid)
        if not mag:
            return 0
        return sum(mag.get("ammo", {}).values())

    def get_magazine_ammo_types(self, uid: str) -> dict:
        mag = self.get_magazine_obj(uid)
        if not mag:
            return {}
        return dict(mag.get("ammo", {}))

    def consume_magazine_ammo(self, uid: str, count: int) -> int:
        mag = self.get_magazine_obj(uid)
        if not mag:
            return 0

        ammo = mag.get("ammo", {})
        remaining = count
        consumed = 0

        for ammo_type in list(ammo.keys()):
            if remaining <= 0:
                break
            current = ammo[ammo_type]
            to_remove = min(current, remaining)
            ammo[ammo_type] = current - to_remove
            remaining -= to_remove
            consumed += to_remove
            if ammo[ammo_type] <= 0:
                del ammo[ammo_type]

        mag["ammo"] = ammo
        return consumed

    def add_magazine_ammo(self, uid: str, ammo_type: str, count: int) -> bool:
        """
        0.4.6.3: ammo_type может быть простым ('экспансивные') или ключом
        ('9x19|экспансивные'). Внутри магазина храним ТОЛЬКО простой тип.
        Проверка калибра обязательна.
        """
        mag = self.get_magazine_obj(uid)
        if not mag:
            return False

        mag_data = MAGAZINES.get(mag["type_id"])
        if not mag_data:
            return False

        mag_caliber = mag_data.get("caliber")

        # 0.4.6.3: разбираем ключ, если пришёл с калибром
        from ..weapon_system.ammo import parse_ammo_key
        from ..weapon_system import get_caliber_ammo_types

        incoming_caliber, plain_type = parse_ammo_key(ammo_type)

        if incoming_caliber is not None and incoming_caliber != mag_caliber:
            logger.warning(
                f"{getattr(self, 'name', '?')}: попытка зарядить '{ammo_type}' "
                f"в магазин калибра '{mag_caliber}' — отказ (калибр не совпадает)"
            )
            return False

        allowed_types = get_caliber_ammo_types(mag_caliber)
        if plain_type not in allowed_types:
            logger.warning(
                f"{getattr(self, 'name', '?')}: тип '{plain_type}' не подходит "
                f"для калибра '{mag_caliber}' — отказ"
            )
            return False

        capacity = mag_data.get("capacity", 0)
        current = sum(mag["ammo"].values())
        if current + count > capacity:
            count = capacity - current
            if count <= 0:
                return False

        mag["ammo"][plain_type] = mag["ammo"].get(plain_type, 0) + count
        return True

    # ==================== SHELL AMMO ====================

    def get_weapon_shell_capacity(self, weapon_id: str = None) -> int:
        wid = weapon_id or self.weapon
        weapon = WEAPONS.get(wid, {})
        return weapon.get('shell_capacity', 0)

    def get_shell_ammo(self, weapon_id: str = None) -> dict:
        wid = weapon_id or self.weapon
        return dict(self.shell_ammo.get(wid, {}))

    def get_shell_ammo_count(self, weapon_id: str = None) -> int:
        ammo = self.get_shell_ammo(weapon_id)
        return sum(ammo.values())

    def get_shell_first_ammo_type(self, weapon_id: str = None) -> str:
        ammo = self.get_shell_ammo(weapon_id)
        for atype in ammo.keys():
            return atype
        return ""

    def reload_shell(self, ammo_type: str, count: int, weapon_id: str = None) -> int:
        """
        0.4.6.3: ammo_type может быть ключом '<caliber>|<type>'.
        Внутри shell_ammo храним ТОЛЬКО простой тип.
        """
        wid = weapon_id or self.weapon
        weapon = WEAPONS.get(wid, {})
        if not weapon.get('shell_loading'):
            return 0

        from ..weapon_system.ammo import parse_ammo_key
        incoming_caliber, plain_type = parse_ammo_key(ammo_type)

        weapon_caliber = weapon.get('caliber')
        if incoming_caliber is not None and incoming_caliber != weapon_caliber:
            logger.warning(
                f"{getattr(self, 'name', '?')}: попытка зарядить '{ammo_type}' в ствол "
                f"калибра '{weapon_caliber}' — отказ"
            )
            return 0

        # Проверяем, что тип разрешён для этого калибра
        from ..weapon_system import get_caliber_ammo_types
        allowed_types = get_caliber_ammo_types(weapon_caliber)
        if plain_type not in allowed_types:
            logger.warning(
                f"{getattr(self, 'name', '?')}: тип '{plain_type}' не подходит "
                f"для калибра '{weapon_caliber}' — отказ"
            )
            return 0

        capacity = weapon.get('shell_capacity', 0)
        current = self.get_shell_ammo_count(wid)
        free = capacity - current

        if free <= 0:
            return 0

        # Достаём из инвентаря по полному ключу (если пришёл ключ — берём его,
        # иначе — формируем из caliber+type)
        inventory_key = ammo_type if incoming_caliber is not None else \
            f"{weapon_caliber}|{plain_type}"

        available = self.inventory.get(inventory_key, 0)
        to_load = min(count, free, available)

        if to_load <= 0:
            return 0

        if wid not in self.shell_ammo:
            self.shell_ammo[wid] = {}
        self.shell_ammo[wid][plain_type] = self.shell_ammo[wid].get(plain_type, 0) + to_load
        self.inventory[inventory_key] = available - to_load

        return to_load

    def consume_shell_ammo(self, count: int = 1, weapon_id: str = None) -> int:
        wid = weapon_id or self.weapon
        if wid not in self.shell_ammo:
            return 0

        ammo = self.shell_ammo[wid]
        consumed = 0

        for atype in list(ammo.keys()):
            if consumed >= count:
                break
            available = ammo[atype]
            take = min(available, count - consumed)
            ammo[atype] -= take
            consumed += take
            if ammo[atype] <= 0:
                del ammo[atype]

        return consumed

    def has_ammo_in_shell(self, weapon_id: str = None) -> bool:
        return self.get_shell_ammo_count(weapon_id) > 0