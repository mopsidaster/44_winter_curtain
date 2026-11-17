# -*- coding: utf-8 -*-
# func/player/_constants.py - Константы и утилиты навыков (0.4.4.8)
#
# Рефакторинг без изменения логики.
# Добавлено логирование через utils.logger.

from utils.logger import get_logger

logger = get_logger()


DEFAULT_SKILLS = {
    "сила": 0,
    "выносливость": 0,
    "стойкость": 0,
    "меткость": 0,
    "здоровье": 0,
    "инженерия": 0,
}


def _normalize_skills(raw) -> dict:
    """
    Привести навыки к словарю с полным набором ключей.
    Отсутствующие ключи заполняются нулями; лишние — игнорируются.
    """
    result = dict(DEFAULT_SKILLS)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in result:
                result[k] = v
            else:
                logger.debug(f"Нормализация навыков: пропущен неизвестный ключ '{k}'")
    elif raw is not None:
        logger.warning(
            f"Нормализация навыков: ожидался dict, получен {type(raw).__name__} — "
            f"использованы дефолтные значения"
        )
    return result