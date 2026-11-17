# -*- coding: utf-8 -*-
# utils/logger.py - Система логирования (Билд 0.4.2.10)
#
# ОПТИМИЗАЦИЯ (патч 0.4.2.10):
#   • Абсолютный путь к logs/ (не зависит от рабочей директории)
#   • INFO в файл (DEBUG флудил при каждом сохранении)
#   • Защита от повторного добавления handlers (при hot-reload)

import logging
import os
import traceback
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs"
)
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger('metro_bot')
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'metro_bot.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False


def get_logger():
    return logger


def log_error(error: Exception, context: str = ""):
    """Логирование ошибки с полным traceback."""
    logger.error(f"ОШИБКА в {context}: {str(error)}")
    logger.error(traceback.format_exc())