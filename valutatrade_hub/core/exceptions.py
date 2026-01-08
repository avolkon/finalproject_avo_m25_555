"""Модуль пользовательских исключений для платформы ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовый класс для всех пользовательских исключений платформы.
    
    Используется для централизованной обработки ошибок и логирования.
    """
    pass


class CurrencyNotFoundError(ValutaTradeError):
    """Исключение при запросе неизвестной/неподдерживаемой валюты.
    Attributes:
        code: Код валюты, который не был найден в системе
    """
    
    def __init__(self, code: str):
        """Инициализация исключения с кодом неизвестной валюты.
        Args:
            code: Код валюты, который не был найден
        """
        # Формирование сообщения об ошибке согласно требованиям ТЗ
        message = f"Неизвестная валюта '{code}'"
        
        # Сохранение кода валюты как атрибута исключения
        self.code = code
        
        # Вызов конструктора родительского класса с сообщением
        super().__init__(message)

class InsufficientFundsError(ValutaTradeError):
    """Исключение при недостатке средств на кошельке для выполнения операции.
    
    Attributes:
        available: Доступный баланс на кошельке
        required: Требуемая сумма для операции
        code: Код валюты операции
    """
    
    def __init__(self, available: float, required: float, code: str):
        """Инициализация исключения с параметрами финансовой операции.
        
        Args:
            available: Текущий доступный баланс на кошельке
            required: Сумма, необходимая для выполнения операции
            code: Код валюты, в которой выполняется операция
            
        Raises:
            ValueError: Если суммы не являются положительными числами
        """
        # Валидация входных параметров
        if available < 0:
            raise ValueError("Доступный баланс не может быть отрицательным")
        if required <= 0:
            raise ValueError("Требуемая сумма должна быть положительной")
        
        # Сохранение параметров как атрибутов исключения
        self._available = available
        self._required = required
        self._code = code.upper()  # Нормализация кода валюты
        
        # Форматирование сообщения об ошибке согласно точному формату ТЗ
        message = (f"Недостаточно средств: доступно {available:.4f} {self._code}, "
                   f"требуется {required:.4f} {self._code}")
        
        # Вызов конструктора родительского класса
        super().__init__(message)
    
    @property
    def available(self) -> float:
        """Получить доступный баланс на кошельке.
        
        Returns:
            Доступная сумма для операции
        """
        return self._available
    
    @property
    def required(self) -> float:
        """Получить требуемую сумму для операции.
        
        Returns:
            Необходимая сумма для выполнения операции
        """
        return self._required
    
    @property
    def code(self) -> str:
        """Получить код валюты операции.
        
        Returns:
            Код валюты в верхнем регистре
        """
        return self._code
    
    @property
    def deficit(self) -> float:
        """Вычислить дефицит средств для выполнения операции.
        
        Returns:
            Разница между требуемой и доступной суммой
        """
        return self._required - self._available


class ApiRequestError(ValutaTradeError):
    """Исключение при сбое внешнего API (например, Parser Service).
    
    Attributes:
        reason: Описание причины ошибки
        status_code: HTTP статус код ответа (если применимо)
    """
    
    def __init__(self, reason: str, status_code: int | None = None):
        """Инициализация исключения с причиной сбоя API.
        
        Args:
            reason: Текстовое описание причины ошибки
            status_code: HTTP статус код ответа сервера (опционально)
            
        Raises:
            ValueError: Если reason пустая строка
        """
        # Валидация причины ошибки
        if not reason or not reason.strip():
            raise ValueError("Причина ошибки API не может быть пустой")
        
        # Сохранение параметров как атрибутов исключения
        self._reason = reason.strip()
        self._status_code = status_code
        
        # Формирование базового сообщения согласно формату ТЗ
        message = f"Ошибка при обращении к внешнему API: {self._reason}"
        
        # Добавление информации о статус коде, если он предоставлен
        if status_code is not None:
            message += f" (код: {status_code})"
        
        # Вызов конструктора родительского класса
        super().__init__(message)
    
    @property
    def reason(self) -> str:
        """Получить описание причины ошибки API.
        
        Returns:
            Текстовое описание причины сбоя
        """
        return self._reason
    
    @property
    def status_code(self) -> int | None:
        """Получить HTTP статус код ответа.
        
        Returns:
            Статус код или None, если не предоставлен
        """
        return self._status_code
    
    