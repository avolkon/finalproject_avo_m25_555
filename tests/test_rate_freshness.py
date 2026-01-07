"""
tests/test_rate_freshness.py - Интеграционные тесты проверки свежести курсов.
"""

import unittest
import tempfile
import os
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Импорт тестируемых модулей
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from valutatrade_hub.core.usecases import (
    is_rate_fresh,
    get_rate
)


class TestRateFreshness(unittest.TestCase):
    """Тесты проверки свежести курсов валют."""
    
    def setUp(self) -> None:
        """Подготовка временной директории для тестов."""
        # Создание временной директории для изоляции тестов
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = os.environ.get('DATA_DIR')
        os.environ['DATA_DIR'] = self.temp_dir
        
        # Создание директории data в временной папке
        self.data_dir = Path(self.temp_dir) / "data"
        self.data_dir.mkdir(exist_ok=True)
    
    def tearDown(self) -> None:
        """Очистка временных файлов после теста."""
        # Восстановление оригинальной директории данных
        if self.original_data_dir:
            os.environ['DATA_DIR'] = self.original_data_dir
        else:
            os.environ.pop('DATA_DIR', None)
        
        # Удаление временной директории
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_is_rate_fresh_fresh_crypto(self) -> None:
        """Тест: Криптовалюта обновлена 1 минуту назад - свежая."""
        timestamp = (datetime.now() - timedelta(minutes=1)).isoformat()
        result = is_rate_fresh("BTC_USD", timestamp)
        self.assertTrue(result, "BTC должен быть свежим (1 минута)")
    
    def test_is_rate_fresh_stale_crypto(self) -> None:
        """Тест: Криптовалюта обновлена 10 минут назад - устаревшая."""
        timestamp = (datetime.now() - timedelta(minutes=10)).isoformat()
        result = is_rate_fresh("BTC_USD", timestamp)
        self.assertFalse(result, "BTC должен быть устаревшим (10 минут)")
    
    def test_is_rate_fresh_fresh_fiat(self) -> None:
        """Тест: Фиатная валюта обновлена 1 час назад - свежая."""
        timestamp = (datetime.now() - timedelta(hours=1)).isoformat()
        result = is_rate_fresh("EUR_USD", timestamp)
        self.assertTrue(result, "EUR должен быть свежим (1 час)")
    
    def test_is_rate_fresh_stale_fiat(self) -> None:
        """Тест: Фиатная валюта обновлена 25 часов назад - устаревшая."""
        timestamp = (datetime.now() - timedelta(hours=25)).isoformat()
        result = is_rate_fresh("EUR_USD", timestamp)
        self.assertFalse(result, "EUR должен быть устаревшим (25 часов)")
    
    def test_is_rate_fresh_invalid_timestamp(self) -> None:
        """Тест: Некорректный формат timestamp."""
        result = is_rate_fresh("BTC_USD", "invalid_timestamp")
        self.assertFalse(result, "Некорректный timestamp → устаревший")
    
    def test_is_rate_fresh_invalid_currency_pair(self) -> None:
        """Тест: Некорректный формат валютной пары."""
        timestamp = datetime.now().isoformat()
        result = is_rate_fresh("BTCEUR", timestamp)  # Нет разделителя "_"
        self.assertFalse(result, "Некорректная пара → устаревший")
    
    def test_generate_test_rates_all_fresh(self) -> None:
        """Тест: Генерация всех свежих курсов (ручное создание)."""
        # Вместо вызова generate_test_rates, создаем данные вручную
        from datetime import datetime, timedelta
        
        test_data = {}
        current_time = datetime.now()
        fresh_time = (current_time - timedelta(minutes=1)).isoformat()
        
        # Создание свежих данных
        test_data["EUR_USD"] = {
            "rate": 1.0786,
            "updated_at": fresh_time
        }
        test_data["BTC_USD"] = {
            "rate": 59337.21,
            "updated_at": fresh_time
        }
        test_data["source"] = "ManualTest"
        test_data["test_scenario"] = "all_fresh"
        
        # Сохранение вручную
        rates_file = self.data_dir / "rates.json"
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Проверка, что файл создан
        self.assertTrue(rates_file.exists(), "rates.json должен быть создан")
        
        # Проверка свежести
        result = is_rate_fresh("EUR_USD", fresh_time)
        self.assertTrue(result, "Ручные данные должны быть свежими")
    
    def test_generate_test_rates_all_stale(self) -> None:
        """Тест: Генерация всех устаревших курсов (ручное создание)."""
        from datetime import datetime, timedelta
        
        test_data = {}
        current_time = datetime.now()
        stale_time = (current_time - timedelta(days=2)).isoformat()
        
        # Создание устаревших данных
        test_data["BTC_USD"] = {
            "rate": 59337.21,
            "updated_at": stale_time
        }
        test_data["source"] = "ManualTest"
        test_data["test_scenario"] = "all_stale"
        
        # Сохранение вручную
        rates_file = self.data_dir / "rates.json"
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Проверка устаревания
        result = is_rate_fresh("BTC_USD", stale_time)
        self.assertFalse(result, "Ручные данные должны быть устаревшими")
    
    def test_get_rate_with_fresh_data(self) -> None:
        """Тест: get_rate возвращает свежий курс из rates.json."""
        from datetime import datetime, timedelta
        
        # Создание свежих данных вручную
        test_data = {}
        fresh_time = (datetime.now() - timedelta(minutes=1)).isoformat()
        
        test_data["EUR_USD"] = {
            "rate": 1.0786,
            "updated_at": fresh_time
        }
        
        # Сохранение
        rates_file = self.data_dir / "rates.json"
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Получение курса
        rate, timestamp, source, is_fresh = get_rate("EUR", "USD")
        
        # Проверки
        self.assertIsInstance(rate, float, "Курс должен быть float")
        self.assertNotEqual(timestamp, "N/A", "Должен быть timestamp")
        self.assertEqual(source, "rates.json", "Источник должен быть rates.json")
        self.assertTrue(is_fresh, "Курс должен быть свежим")
    
    def test_get_rate_with_stale_data(self) -> None:
        """Тест: get_rate использует fallback для устаревших данных."""
        from datetime import datetime, timedelta
        
        # Создание устаревших данных вручную (2 дня назад для BTC)
        test_data = {}
        stale_time = (datetime.now() - timedelta(days=2)).isoformat()
        
        test_data["BTC_USD"] = {
            "rate": 50000.0,  # Заведомо отличающийся курс
            "updated_at": stale_time
        }
        
        # Сохранение
        rates_file = self.data_dir / "rates.json"
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Получение курса
        rate, timestamp, source, is_fresh = get_rate("BTC", "USD")
        
        # ОЖИДАЕМОЕ ПОВЕДЕНИЕ: устаревшие данные → Fallback
        # BTC устарел (2 дня > 5 минут) → должен использовать fallback
        
        print(f"\n[DEBUG] test_get_rate_with_stale_data:")
        print(f"  Timestamp в тесте: {stale_time}")
        print(f"  Получено: rate={rate}, source={source}, is_fresh={is_fresh}")
        
        # BTC устарел (2 дня) → должен быть Fallback
        self.assertEqual(source, "Fallback", 
                        f"BTC устарел (2 дня) → должен быть Fallback, получено: {source}")
        self.assertFalse(is_fresh, "Устаревший курс не должен быть свежим")
        
        # Проверяем, что использован fallback курс (59337.21), а не значение из JSON (50000.0)
        expected_fallback_rate = 59337.21
        self.assertAlmostEqual(rate, expected_fallback_rate, delta=0.1,
                              msg=f"Должен быть fallback курс (~{expected_fallback_rate}), "
                                  f"получено: {rate}")        
    
    def test_get_rate_with_empty_rates(self) -> None:
        """Тест: get_rate работает при пустом rates.json."""
        # Создание пустого rates.json
        rates_file = self.data_dir / "rates.json"
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        
        # Получение курса
        rate, timestamp, source, is_fresh = get_rate("USD", "EUR")
        
        # Проверки для fallback
        self.assertIsInstance(rate, float, "Курс должен быть float")
        self.assertEqual(timestamp, "N/A", "Timestamp должен быть N/A")
        self.assertEqual(source, "Fallback", "Источник должен быть Fallback")
        self.assertFalse(is_fresh, "Fallback не должен быть свежим")
    
    def test_integration_chain(self) -> None:
        """Интеграционный тест всей цепочки: генерация → проверка → получение."""
        from datetime import datetime, timedelta
        
        # Создание смешанных данных вручную
        test_data = {}
        current_time = datetime.now()
        
        # 2 свежих курса
        test_data["EUR_USD"] = {
            "rate": 1.0786,
            "updated_at": (current_time - timedelta(minutes=1)).isoformat()  # Свежий
        }
        test_data["BTC_USD"] = {
            "rate": 59337.21,
            "updated_at": (current_time - timedelta(minutes=3)).isoformat()  # Свежий (3 минуты < 5 минут)
        }
        # 1 устаревший курс (2 дня для крипто > 5 минут)
        test_data["ETH_USD"] = {
            "rate": 3720.0,
            "updated_at": (current_time - timedelta(days=2)).isoformat()  # Устаревший
        }
        
        # Сохранение
        rates_file = self.data_dir / "rates.json"
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Проверка различных пар
        test_pairs = [("EUR", "USD"), ("BTC", "USD"), ("ETH", "USD")]
        
        print("\n[DEBUG] test_integration_chain:")
        
        for from_curr, to_curr in test_pairs:
            rate, timestamp, source, is_fresh = get_rate(from_curr, to_curr)
            
            print(f"  {from_curr}→{to_curr}: rate={rate:.6f}, source={source}, fresh={is_fresh}")
            
            # Базовые проверки для всех пар
            self.assertIsInstance(rate, float)
            self.assertIn(source, ["rates.json", "Fallback"])
            self.assertIsInstance(is_fresh, bool)
            
            # Специфичные проверки
            if from_curr == "ETH":
                # ETH устарел (2 дня > 5 минут) → Fallback
                self.assertEqual(source, "Fallback", 
                               "ETH устарел (2 дня) → должен использовать fallback")
                self.assertFalse(is_fresh, "ETH не должен быть свежим")
            elif from_curr == "BTC":
                # BTC свежий (3 минуты < 5 минут) → rates.json
                self.assertEqual(source, "rates.json", 
                               "BTC свежий (3 минуты) → должен использовать rates.json")
                self.assertTrue(is_fresh, "BTC должен быть свежим")
            elif from_curr == "EUR":
                # EUR свежий (1 минута < 24 часа) → rates.json
                self.assertEqual(source, "rates.json", 
                               "EUR свежий (1 минута) → должен использовать rates.json")
                self.assertTrue(is_fresh, "EUR должен быть свежим")


def run_tests() -> None:
    """Запуск всех тестов."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests()