import os
import time
import requests  # type: ignore
import logging
import sys

from dotenv import load_dotenv  # type: ignore
from telebot import TeleBot  # type: ignore


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

logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='UTF-8'
)

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет наличие токенов и id."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]

    if missing_tokens:
        logger.critical(
            f'Отсутствуют обязательные переменные: {", ".join(missing_tokens)}'
        )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение отправлено: {message}')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API Практикума."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            logger.warning(
                f'Практикум недоступен. Код ответа API: {response.status_code}'
            )
            raise requests.RequestException(
                f'Практикум недоступен. Код ответа API: {response.status_code}'
            )
        logger.debug('Запрос к Практикуму прошел успешно')
        return response.json()
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к Практикуму: {error}')
        raise ConnectionError
    except ValueError as error:
        logger.error(f'Ошибка парсинга JSON: {error}')
        raise ValueError(f'Ошибка парсинга JSON: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем')
        raise TypeError('Ответ API не является словарем')

    if 'homeworks' not in response or 'current_date' not in response:
        logger.error('В ответе API отсутствуют ожидаемые ключи')
        raise KeyError('В ответе API отсутствуют ожидаемые ключи')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('homeworks в ответе API не является списком')
        raise TypeError('homeworks в ответе API не является списком')

    return homeworks


def parse_status(homework):
    """Проверяет статус ревью."""
    if not isinstance(homework, dict):
        logger.error('homework не является словарем')
        raise TypeError('homework не является словарем')

    required_keys = ['homework_name', 'status']
    for key in required_keys:
        if key not in homework:
            logger.error(f'В homework отсутствует ключ {key}')
            raise KeyError(f'В homework отсутствует ключ {key}')

    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Неизвестный статус работы: {status}')
        raise ValueError(f'Неизвестный статус работы: {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
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
                send_message(bot, message)
            else:
                logger.debug('Новых статусов нет')

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if str(error) != last_error:
                send_message(bot, message)
                last_error = str(error)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
