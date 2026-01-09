"""
Модуль планировщика автоматического обновления курсов валют.
"""

import logging
import threading
import signal
import time
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from .updater import RatesUpdater, UpdateResult
from .config import config
from valutatrade_hub.core.exceptions import ApiRequestError


@dataclass
class SchedulerStatus:
    """Статус планировщика обновлений."""
    is_running: bool  # Флаг работы планировщика
    last_fiat_update: Optional[str]  # Время последнего обновления фиата
    last_crypto_update: Optional[str]  # Время последнего обновления крипто
    next_fiat_update: Optional[str]  # Время следующего обновления фиата
    next_crypto_update: Optional[str]  # Время следующего обновления крипто
    total_updates: int  # Всего выполненных обновлений
    failed_updates: int  # Неудачных обновлений


class RatesScheduler:
    """Планировщик автоматического обновления курсов валют."""

    def __init__(self, updater: RatesUpdater) -> None:
        """Инициализация планировщика обновлений.

        Args:
            updater: Экземпляр RatesUpdater для выполнения обновлений
        """
        self.updater = updater  # Координатор обновления курсов
        self.logger = logging.getLogger("parser.scheduler")  # Логгер
        
        # Загрузка интервалов из конфигурации
        self.fiat_interval_seconds = (
            config.FIAT_UPDATE_INTERVAL_MINUTES * 60
        )
        self.crypto_interval_seconds = (
            config.CRYPTO_UPDATE_INTERVAL_MINUTES * 60
        )
        
        # Состояние планировщика
        self._running = False  # Флаг работы планировщика
        self._timers: List[threading.Timer] = []  # Список активных таймеров
        self._update_in_progress = False  # Флаг выполняющегося обновления
        
        # Статистика работы
        self.status = SchedulerStatus(
            is_running=False,
            last_fiat_update=None,
            last_crypto_update=None,
            next_fiat_update=None,
            next_crypto_update=None,
            total_updates=0,
            failed_updates=0,
        )
        
        # Настройка обработки сигналов для graceful shutdown
        self._setup_signal_handlers()
        
        self.logger.info(
            f"Планировщик инициализирован: фиат={self.fiat_interval_seconds}с, "
            f"крипто={self.crypto_interval_seconds}с"
        )

    def start(self) -> None:
        """Запустить планировщик обновлений."""
        if self._running:
            self.logger.warning("Планировщик уже запущен")
            return
        
        self._running = True
        self.status.is_running = True
        
        # Логирование запуска
        self.logger.info(
            f"Запуск планировщика: фиат каждые "
            f"{config.FIAT_UPDATE_INTERVAL_MINUTES} мин, "
            f"крипто каждые {config.CRYPTO_UPDATE_INTERVAL_MINUTES} мин"
        )
        
        # Планирование первого обновления
        self._schedule_fiat_update(delay_seconds=0)  # Немедленно
        self._schedule_crypto_update(delay_seconds=0)  # Немедленно
        
        # Логирование расписания
        self._log_next_schedule()
        
        # Ожидание завершения (если планировщик работает в основном потоке)
        if threading.current_thread() == threading.main_thread():
            self._wait_for_shutdown()

    def stop(self) -> None:
        """Остановить планировщик обновлений."""
        if not self._running:
            self.logger.warning("Планировщик уже остановлен")
            return
        
        self.logger.info("Остановка планировщика...")
        self._running = False
        self.status.is_running = False
        
        # Отмена всех активных таймеров
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()
        
        # Ожидание завершения текущего обновления
        if self._update_in_progress:
            self.logger.info("Ожидание завершения текущего обновления...")
            time.sleep(1)  # Краткая пауза
        
        self.logger.info(
            f"Планировщик остановлен. Всего обновлений: "
            f"{self.status.total_updates}, ошибок: {self.status.failed_updates}"
        )

    def get_status(self) -> SchedulerStatus:
        """Получить текущий статус планировщика.

        Returns:
            Копия текущего статуса планировщика
        """
        return SchedulerStatus(
            is_running=self.status.is_running,
            last_fiat_update=self.status.last_fiat_update,
            last_crypto_update=self.status.last_crypto_update,
            next_fiat_update=self.status.next_fiat_update,
            next_crypto_update=self.status.next_crypto_update,
            total_updates=self.status.total_updates,
            failed_updates=self.status.failed_updates,
        )

    def _schedule_fiat_update(self, delay_seconds: Optional[int] = None) -> None:
        """Запланировать обновление фиатных курсов.

        Args:
            delay_seconds: Задержка перед обновлением в секундах
                          (по умолчанию интервал из конфигурации)
        """
        if not self._running:
            return
        
        # Использование интервала из конфигурации если задержка не указана
        if delay_seconds is None:
            delay_seconds = self.fiat_interval_seconds
        
        # Создание и запуск таймера
        timer = threading.Timer(
            delay_seconds,
            self._run_scheduled_update,
            kwargs={"source_type": "fiat"}
        )
        timer.daemon = True  # Демон-поток для автоматического завершения
        timer.start()
        self._timers.append(timer)
        
        # Обновление статуса следующего обновления
        next_update_time = datetime.now().timestamp() + delay_seconds
        self.status.next_fiat_update = datetime.fromtimestamp(
            next_update_time
        ).isoformat()

    def _schedule_crypto_update(self, delay_seconds: Optional[int] = None) -> None:
        """Запланировать обновление криптовалютных курсов.

        Args:
            delay_seconds: Задержка перед обновлением в секундах
                          (по умолчанию интервал из конфигурации)
        """
        if not self._running:
            return
        
        # Использование интервала из конфигурации если задержка не указана
        if delay_seconds is None:
            delay_seconds = self.crypto_interval_seconds
        
        # Создание и запуск таймера
        timer = threading.Timer(
            delay_seconds,
            self._run_scheduled_update,
            kwargs={"source_type": "crypto"}
        )
        timer.daemon = True  # Демон-поток для автоматического завершения
        timer.start()
        self._timers.append(timer)
        
        # Обновление статуса следующего обновления
        next_update_time = datetime.now().timestamp() + delay_seconds
        self.status.next_crypto_update = datetime.fromtimestamp(
            next_update_time
        ).isoformat()

    def _run_scheduled_update(self, source_type: str) -> None:
        """Выполнить запланированное обновление курсов.

        Args:
            source_type: Тип обновления ('fiat' или 'crypto')
        """
        # Проверка флага работы планировщика
        if not self._running:
            return
        
        # Проверка на параллельные обновления
        if self._update_in_progress and not config.ALLOW_CONCURRENT_UPDATES:
            self.logger.warning(
                f"Пропущено обновление {source_type}: "
                f"другое обновление уже выполняется"
            )
            # Повторное планирование через короткий интервал
            retry_delay = 30  # 30 секунд
            if source_type == "fiat":
                self._schedule_fiat_update(delay_seconds=retry_delay)
            else:
                self._schedule_crypto_update(delay_seconds=retry_delay)
            return
        
        # Установка флага выполняющегося обновления
        self._update_in_progress = True
        
        try:
            # Определение источника для обновления
            source_name = (
                "ExchangeRate" if source_type == "fiat" else "CoinGecko"
            )
            current_time = datetime.now().isoformat()
            
            # Логирование начала обновления
            self.logger.info(
                f"Начало запланированного обновления {source_type} "
                f"({source_name}) в {current_time}"
            )
            
            # Выполнение обновления
            result = self.updater.run_update_for_source(source_name)
            self.status.total_updates += 1
            
            # Обновление времени последнего обновления
            if source_type == "fiat":
                self.status.last_fiat_update = current_time
            else:
                self.status.last_crypto_update = current_time
            
            # Обработка результата обновления
            if result.status.name == "FAILED":
                self.status.failed_updates += 1
                self.logger.error(
                    f"Ошибка обновления {source_type}: {result.error_messages}"
                )
            else:
                self.logger.info(
                    f"Обновление {source_type} завершено: "
                    f"{result.total_rates} курсов"
                )
            
        except ApiRequestError as e:
            # Ошибка API при обновлении
            self.status.failed_updates += 1
            self.logger.error(f"Ошибка API при обновлении {source_type}: {e}")
            
        except Exception as e:
            # Неожиданная ошибка при обновлении
            self.status.failed_updates += 1
            self.logger.error(
                f"Неожиданная ошибка при обновлении {source_type}: {e}",
                exc_info=True
            )
            
        finally:
            # Сброс флага выполняющегося обновления
            self._update_in_progress = False
            
            # Планирование следующего обновления
            if self._running:
                if source_type == "fiat":
                    self._schedule_fiat_update()
                else:
                    self._schedule_crypto_update()

    def _setup_signal_handlers(self) -> None:
        """Настройка обработчиков сигналов для graceful shutdown."""
        def signal_handler(signum, frame):
            """Обработчик сигнала для graceful shutdown."""
            signal_name = signal.Signals(signum).name
            self.logger.info(f"Получен сигнал {signal_name}, остановка...")
            self.stop()
            # Выход из приложения после остановки планировщика
            raise SystemExit(0)
        
        # Регистрация обработчиков для SIGINT (Ctrl+C) и SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self.logger.debug("Обработчики сигналов настроены")

    def _wait_for_shutdown(self) -> None:
        """Ожидание сигнала завершения в основном потоке."""
        try:
            # Бесконечное ожидание в основном потоке
            while self._running:
                time.sleep(1)  # Краткая пауза для уменьшения нагрузки CPU
                
                # Периодическое логирование статуса (раз в минуту)
                if int(time.time()) % 60 == 0:
                    self._log_status()
                    
        except KeyboardInterrupt:
            # Обработка Ctrl+C в основном потоке
            self.logger.info("Получен KeyboardInterrupt, остановка...")
            self.stop()
            
        except Exception as e:
            # Неожиданная ошибка в основном потоке
            self.logger.error(f"Ошибка в основном потоке: {e}")
            self.stop()
            raise

    def _log_next_schedule(self) -> None:
        """Логирование расписания следующих обновлений."""
        if self.status.next_fiat_update:
            self.logger.info(
                f"Следующее обновление фиата: {self.status.next_fiat_update}"
            )
        if self.status.next_crypto_update:
            self.logger.info(
                "Следующее обновление крипто: "
                f"{self.status.next_crypto_update}"
            )

    def _log_status(self) -> None:
        """Логирование текущего статуса планировщика."""
        status_msg = (
            f"Статус: запущен={self._running}, "
            f"обновлений={self.status.total_updates}, "
            f"ошибок={self.status.failed_updates}"
        )
        
        if self.status.last_fiat_update:
            status_msg += f", фиат={self.status.last_fiat_update[11:19]}"
        if self.status.last_crypto_update:
            status_msg += f", крипто={self.status.last_crypto_update[11:19]}"
        
        self.logger.info(status_msg)


# Экспорт публичных классов модуля
__all__ = [
    "SchedulerStatus",  # Статус планировщика
    "RatesScheduler",  # Основной класс планировщика
]

