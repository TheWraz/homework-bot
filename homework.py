import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

import requests  # type: ignore
import telebot.apihelper  # type: ignore
from dotenv import load_dotenv  # type: ignore
from telebot import TeleBot  # type: ignore
import requests.exceptions  # type: ignore

from exceptions import (
    APIConnectionError,
    APIStatusCodeError,
    TokensError,
)  # я просто забываю про импорты) собираюсь в конце поправить их всегда и ...


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
))
logger.addHandler(stream_handler)

file_handler = RotatingFileHandler('homework.log', encoding='UTF-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
))
logger.addHandler(file_handler)


def check_tokens():
    """Проверяет наличие токенов и id."""
    required_tokens = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    missing_tokens = [
        token for token in required_tokens if not globals().get(token)
    ]

    if missing_tokens:
        error_message = f'Отсутствуют обязательные переменные: {
            ", ".join(missing_tokens)
        }'
        logger.critical(error_message)
        raise TokensError(error_message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.debug(f'Попытка отправки сообщения: {message}')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except (
        telebot.apihelper.ApiException,
        requests.exceptions.RequestException
    ) as error:
        logger.error(f'Ошибка при отправке сообщения в Telegram: {error}')
        raise


def get_api_answer(timestamp):
    """Делает запрос к API Практикума."""
    params = {'from_date': timestamp}
    logger.debug(f'Отправка запроса к {ENDPOINT} с параметрами: {params}')

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=10
        )
    except requests.RequestException as error:
        raise APIConnectionError(f'Ошибка подключения к API: {error}')

    if response.status_code != requests.codes.ok:
        raise APIStatusCodeError(
            f'Неожиданный статус код {response.status_code} от API'
        )

    result = response.json()
    logger.debug('Успешный запрос и парсинг ответа API')
    return result


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Начало проверки ответа API')

    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарем, а получен {
                type(response).__name__
            }'
        )

    if 'homeworks' not in response:
        raise KeyError(
            'В ответе API отсутствует обязательный ключ "homeworks"'
        )

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'homeworks должен быть списком, а получен {
                type(homeworks).__name__
            }'
        )

    logger.debug('Проверка ответа API успешно завершена')
    return homeworks


def parse_status(homework):
    """Проверяет статус ревью."""
    logger.debug('Начало проверки статуса ревью')
    if not isinstance(homework, dict):
        raise TypeError(
            f'homework должен быть словарем, а получен {
                type(homework).__name__
            }'
        )

    required_keys = ['homework_name', 'status']
    for key in required_keys:
        if key not in homework:
            raise KeyError(f'В homework отсутствует ключ {key}')

    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except TokensError as error:
        logger.critical(f'Программа остановлена: {error}')
        sys.exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    last_error = None
            else:
                logger.debug('Новых статусов нет')

            timestamp = response.get('current_date', int(time.time()))

        except (
            APIConnectionError,
            APIStatusCodeError,
            TypeError,
            ValueError,
            KeyError
        ) as error:
            error_message = str(error)
            if error_message != last_error:
                logger.error(error_message)
                if send_message(bot, error_message):
                    last_error = error_message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
