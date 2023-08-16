import logging
import os

import requests

import telegram
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='my_bot.log',
    format='%(asctime)s - %(levelname)s - %(message)s'
)


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
    if not PRACTICUM_TOKEN:
        logging.critical('Не найдена переменная PRACTICUM_TOKEN')
        raise ValueError('Не найдена переменная PRACTICUM_TOKEN')
    if not TELEGRAM_TOKEN:
        logging.critical('Не найдена переменная TELEGRAM_TOKEN')
        raise ValueError('Не найдена переменная TELEGRAM_TOKEN')
    if not TELEGRAM_CHAT_ID:
        logging.critical('Не найдена переменная TELEGRAM_CHAT_ID')
        raise ValueError('Не найдена переменная TELEGRAM_CHAT_ID')


class TelegramError(Exception):
    """Ошибка при отправке сообщения."""
    pass


def send_message(bot, message):
    """Отправка сообщения пользователю."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено')
    except TelegramError as error:
        logging.error(f'Сбой при отправке сообщения - {error}')


def get_api_answer(timestamp):
    """Получение ответа от API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
        response.raise_for_status()
        if response.status_code != 200:
            logging.error(
                f'Получен ответ с кодом состояния: {response.status_code}')
            raise requests.RequestException(
                'Получен статус ответа, отличный от 200')
    except requests.RequestException:
        logging.error(
            f'Получен ответ с кодом состояния: {response.status_code}')
        raise requests.RequestException(
            'Получен статус ответа, отличный от 200')
    response = response.json()
    return response


def check_response(response):
    """Проверка ответа от API на соответствие документации."""
    if 'homeworks' not in response:
        logging.error('Домашняя работа отсутствует в объекте ответа')
        raise TypeError('Домашняя работа отсутствует в объекте ответа')
    if type(response) != dict:
        raise TypeError(
            'Структура полученных данных не соответствует ожидаемой')
    if type(response['homeworks']) != list:
        raise TypeError(
            'Структура полученных данных не соответствует ожидаемой')
    for homework in response['homeworks']:
        if 'status' not in homework:
            logging.error('В ответе API отсутствуют данные о проверке работы')
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
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 1549962000

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            for homework in response['homeworks']:
                message = parse_status(homework)
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(f'Сбой при отправке сообщения - {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    """Код, исполняемый только в случае непосредственного запуска."""
    main()
