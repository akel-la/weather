"""
Скрипт, который первым аргументом принимает
название города и выводит текущую погоду.
"""
import argparse
import os
from abc import ABC, abstractmethod

import requests
from dotenv import load_dotenv

load_dotenv()
TEMP_SYMBOL = {"metric": "°C", "standard": "K", "imperial": "°F"}

# Аргументы командной строки:

parser = argparse.ArgumentParser(
        description = (
            "Скрипт, который первым аргументом принимает "
            "название города и выводит текущую погоду."
            ),
        )

parser.add_argument(
        "city",
         help = (
             "Первый аргумент командной строки - имя города"
             " в верхнем или нижнем регистре."
             ),
)
parser.add_argument(
        "--country",
        default = None,
        help = "Необязательный второй аргумент, код страны, например RU.",
)
parser.add_argument(
        "--units",
        default = "metric",
        choices = ["metric", "standard", "imperial"],
        help = f"Единицы измерения:\n"
               f"metric (по умолчанию): Градусы Цельсия, {TEMP_SYMBOL['metric']}\n"
               f"standard: Кельвины, {TEMP_SYMBOL['standard']}\n"
               f"imperial: Градусы Фаренгейта, {TEMP_SYMBOL['imperial']}\n",
)
parser.add_argument(
        "--lang",
        choices = ["ru", "en", "de", "fr"],
        default = "ru",
        help="Язык описания погоды, по умолчанию: ru.",
)

# API и Сервисный уровень:

class ABCWeatherHandler(ABC):
    """Каждый класс - это одна версия API для запросов к тому или иному сервису"""
    # Нужно None, иначе __init_subclass__ придется усложнять:
    URL = None
    _registry = {}


    def __init__(self, api_key):
        self.api_key = api_key


    def __init_subclass__(cls, **kwargs):
        """Вызывается при создании любого подкласса, добавляя его в регистр."""
        super().__init_subclass__(**kwargs)
        if cls.URL is None:
            # По классификации тут TypeError, но вместо него SystemExit, чтобы его
            # перехватывали и выводили ошибку без стека вызовов и прочего подобного:
            raise SystemExit(
                    f"[ОШИБКА АРХИТЕКТУРЫ] Класс {cls.__name__}"
                    " обязан определить атрибут URL"
                    )
        cls._registry[cls.__name__] = cls


    @classmethod
    def create_active(cls):
        """Единая точка входа для создания нужного хендлера."""
        handler_name = os.getenv("ACTIVE_HANDLER")

        handler_class = cls._registry.get(handler_name)
        if not handler_class:
            raise SystemExit(
                    f"[Ошибка]: Класса {handler_name},"
                    f" который указан в .env, не реализован."
                    )

        env_key_name = f"{handler_name.upper()}_API_KEY"
        # "" как значение по умолчанию - чтобы не падал при strip, если будет None,
        # а strip - чтобы отсекать случайные невидимые пробелы в .env:
        api_key = os.getenv(env_key_name, "").strip()

        if not api_key:
            raise SystemExit(
                    f"[ОШИБКА]: Не найден API ключ"
                    f" в переменной {env_key_name}"
                    )
        return handler_class(api_key)

    @abstractmethod
    def get_weather(self, args: dict):
        """Возвращает данные о погоде."""
        pass


class OpenWeather25Handler(ABCWeatherHandler):
    """OpenWeather, API 2.5"""
    URL = "https://api.openweathermap.org/data/2.5/weather"

    def _error_response(self, message, code=500):
        """Вспомогательный метод - словарь сообщения об ошибках"""
        return {"error": message, "status_code": code}

    def get_weather(self, args: dict):

        q = f"{args['city']}"
        if args["country"]:
            q = q + f",{args['country']}"

        weather_params = {
            "q": q,
            "units": args["units"],
            "lang": args["lang"],
            "appid": self.api_key,
        }

        try:
            # timeout - чтобы программа не могла бесконечто ожидать ответа от сервера:
            response = requests.get(self.URL, params = weather_params, timeout = 5)
            data = response.json()

            # Корректный ответ по API:
            if response.status_code == 200:

                actual_country = data.get("sys", {}).get("country")

                if args["country"] and args["country"].upper() != actual_country:
                    return self._error_response(
                            f"Город '{args['city']}' не найден"
                            f"в стране '{args['country']}'",
                            404
                    )

                return {
                    "temp": data["main"]["temp"],
                    "desc": data["weather"][0]["description"],
                    "unit": TEMP_SYMBOL[args["units"]],
                }

            # Город / страна не найдены:
            error_msg = data.get("message", "Неизвестная ошибка API")
            return self._error_response(error_msg, response.status_code)

        except request.exceptions.Timeout:
            return self._error_response(
                    "Превышено время ожидания"
                    " ответа от сервера",
                    500
                    )
        except Exception as e:
            raise SystemExit(f"[ОШИБКА]: Неизвестная ошибка: {e}", 500)

# Запуск и вывод:

if __name__ == "__main__":
    args = vars(parser.parse_args())
    try:
        handler = ABCWeatherHandler.create_active()
        result = handler.get_weather(args)

        if "error" not in result:
            print(
                f"В городе {args['city']} сейчас {result['temp']}"
                f"{result['unit']}, {result['desc']}."
            )
        else:
            print(
                f"[Ошибка]:\nКод ошибки: {result['status_code']}\n"
                f"Сообщение: {result['error']}"
                )
    except SystemExit as e:
        print(e)
    except Exception as e:
        print(f"[Ошибка]: Критический сбой программы: {e}")

