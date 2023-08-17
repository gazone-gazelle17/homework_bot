import logging
import os
import time

import requests

import telegram

from dotenv import load_dotenv
from http import HTTPStatus

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


def check_tokens():
    """Проверка доступности переменных окружения."""
    if PRACTICUM_TOKEN is None:
        raise ValueError('Не найдена переменная PRACTICUM_TOKEN')
    if TELEGRAM_TOKEN is None:
        raise ValueError('Не найдена переменная TELEGRAM_TOKEN')
    if TELEGRAM_CHAT_ID is None:
        raise ValueError('Не найдена переменная TELEGRAM_CHAT_ID')


class TelegramError(Exception):
    """Ошибка при отправке сообщения."""

    pass


def send_message(bot, message):
    """Отправка сообщения пользователю."""
    try:
        logging.debug('Попытка отправить сообщение.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено')
    except TelegramError as error:
        logging.error(f'Сбой при отправке сообщения - {error}')


def get_api_answer(timestamp):
    """Получение ответа от API."""
    try:
        logging.debug(
            f'Отправляем запрос на адрес {ENDPOINT};'
            f'Передаем заголовки с параметром {HEADERS};'
            f'В качестве временной метки принимаем {timestamp};'
        )
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f'Получен ответ с кодом состояния: {response.status_code}')
            raise requests.RequestException(
                'Получен статус ответа, отличный от 200')
    except requests.RequestException:
        logging.error(
            f'Получен ответ с кодом состояния: {response.status_code}')
        raise TelegramError(
            'Получен статус ответа, отличный от 200')
    return response.json()


def check_response(response):
    """Проверка ответа от API на соответствие документации."""
    if 'homeworks' not in response:
        raise TypeError('Домашняя работа отсутствует в объекте ответа')
    if not isinstance(response, dict):
        raise TypeError(
            'Структура полученных данных не соответствует ожидаемой')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Структура полученных данных не соответствует ожидаемой')
    for homework in response['homeworks']:
        if 'status' not in homework:
            raise TypeError(
                'В ответе API отсутствуют данные о проверке работы')
    verdict_keys = HOMEWORK_VERDICTS.keys()
    if homework['status'] not in verdict_keys:
        logging.error(
            f'Значение ключа {response["status"]} недопустимо.'
            f'Допустимые значения: {", ".join(verdict_keys)}'
        )
        raise TypeError(
            f'Значение ключа {response["status"]} недопустимо.'
            f'Допустимые значения: {", ".join(verdict_keys)}'
        )


def parse_status(homework):
    """Распаковка статуса из полученного ответа."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('Домашняя работа не найдена в объекте ответа')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logging.error(f'Неожиданный статус домашней работы - {status}')
        raise KeyError('Статус домашней работы не обнаружен')
    verdict = HOMEWORK_VERDICTS.get(status, 'Статус неизвестен')
    return (f'Изменился статус проверки работы "{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = time.time()
    except ValueError:
        logging.critical('Отсутствуют переменные окружения.')
        raise ValueError('Отсутствуют переменные окружения.')

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            for homework in response['homeworks']:
                message = parse_status(homework)
                send_message(bot, message)

        except Exception as error:
            logging.error(f'Сбой при отправке сообщения - {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    """Код, исполняемый только в случае непосредственного запуска."""
    logging.basicConfig(
        level=logging.DEBUG,
        filename='my_bot.log',
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
