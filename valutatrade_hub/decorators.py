"""Модуль декораторов для платформы ValutaTrade Hub."""

import logging
import time
from functools import wraps
from typing import Callable, Any, Optional, Dict, Tuple
import inspect


def log_action(action: Optional[str] = None, verbose: bool = False) -> Callable:
    """Декоратор для автоматического логирования доменных операций.
    
    Args:
        action: Название операции для логирования (например, 'BUY', 'SELL').
                Если не указано, используется имя декорируемой функции.
        verbose: Режим детального логирования с дополнительным контекстом.
    
    Returns:
        Декоратор, который оборачивает функцию логированием.
        
    Example:
        @log_action(action='BUY', verbose=True)
        def buy_currency(user_id: int, currency_code: str, amount: float):
            # Реализация покупки валюты
            pass
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Tuple[Any, ...], **kwargs: Dict[str, Any]) -> Any:
            """Внутренняя функция-обёртка с логированием операции.
            
            Args:
                *args: Позиционные аргументы декорируемой функции
                **kwargs: Именованные аргументы декорируемой функции
                
            Returns:
                Результат выполнения декорируемой функции
                
            Raises:
                Любые исключения, возникшие в декорируемой функции
            """
            # Получение логгера 'actions' из настроенной системы логирования
            logger = logging.getLogger('actions')
            
            # Определение имени операции для логирования
            action_name = action or func.__name__.upper()
            
            # Извлечение контекста операции из аргументов функции
            context = _extract_context(func, args, kwargs)
            
            # Добавление базовых полей в контекст логирования
            log_context = {
                'action': action_name,
                **context
            }
            
            # Логирование начала операции (только в verbose режиме)
            if verbose:
                logger.debug(f"Начало операции {action_name}", extra=log_context)
                start_time = time.time()  # Запись времени начала для измерения длительности
            
            try:
                # Вызов оригинальной декорируемой функции
                result = func(*args, **kwargs)
                
                # Добавление информации о результате операции
                log_context['result'] = 'OK'
                
                # Добавление значения результата если оно есть (для некоторых операций)
                if result is not None and verbose:
                    # Преобразование результата в строку для логирования
                    log_context['result_value'] = str(result)
                
                # Логирование успешного выполнения операции
                logger.info(f"Операция {action_name} выполнена успешно", 
                           extra=log_context)
                
                # Возврат результата оригинальной функции
                return result
                
            except Exception as e:
                # Добавление информации об ошибке в контекст
                log_context.update({
                    'result': 'ERROR',
                    'error_type': e.__class__.__name__,
                    'error_message': str(e)
                })
                
                # Логирование ошибки операции
                # exc_info=verbose включает stacktrace только в verbose режиме
                logger.error(f"Ошибка операции {action_name}: {e}", 
                            extra=log_context,
                            exc_info=verbose)
                
                # Проброс исключения дальше (декоратор не глотает исключения)
                raise
            
            finally:
                # Дополнительное логирование в verbose режиме (время выполнения)
                if verbose and 'start_time' in locals():
                    execution_time = time.time() - start_time
                    logger.debug(
                        f"Операция {action_name} завершена за {execution_time:.3f} секунд",
                        extra={**log_context, 'execution_time': execution_time}
                    )
        
        return wrapper
    
    return decorator


def _extract_context(func: Callable, args: Tuple[Any, ...], 
                     kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение контекста операции из аргументов декорируемой функции.
    
    Args:
        func: Декорируемая функция для анализа сигнатуры
        args: Кортеж позиционных аргументов функции
        kwargs: Словарь именованных аргументов функции
    
    Returns:
        Словарь с извлечённым контекстом операции
        
    Note:
        Функция анализирует сигнатуру декорируемой функции и извлекает
        часто используемые параметры доменных операций.
    """
    context: Dict[str, Any] = {}
    
    try:
        # Получение сигнатуры функции для анализа параметров
        sig = inspect.signature(func)
        
        # Связывание переданных аргументов с параметрами функции
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()  # Применение значений по умолчанию
        
        # Извлечение часто используемых параметров доменных операций
        for param_name, param_value in bound_args.arguments.items():
            # Проверка параметров которые могут быть полезны для логирования
            if param_name in ['user_id', 'username']:
                context['user'] = param_value
            elif param_name in ['currency_code', 'currency']:
                context['currency_code'] = (
                    param_value.upper() if isinstance(param_value, str) 
                    else param_value
                )
            elif param_name == 'amount':
                context['amount'] = float(param_value) if param_value else 0.0
            elif param_name in ['rate', 'base']:
                context[param_name] = param_value
            
            # Также извлекаем дополнительные параметры для логирования
            elif param_name in ['from_currency', 'to_currency', 'password']:
                # Для параметра password показываем только наличие (без значения)
                if param_name == 'password' and param_value:
                    context['has_password'] = True
                elif param_name != 'password':
                    context[param_name] = param_value
    
    except (TypeError, ValueError) as e:
        # В случае ошибки анализа сигнатуры возвращаем пустой контекст
        logging.getLogger('actions').warning(
            f"Не удалось извлечь контекст для функции {func.__name__}: {e}"
        )
    
    return context


# Пример использования декоратора (документационный)
def _example_usage() -> None:
    """Пример использования декоратора @log_action.
    
    Этот код не выполняется, служит только для документации.
    """
    
    @log_action(action='BUY', verbose=True)
    def example_buy_currency(user_id: int, currency_code: str, amount: float) -> str:
        """Пример функции покупки валюты."""
        return f"Куплено {amount} {currency_code}"
    
    @log_action()  # Без указания action - используется имя функции
    def example_sell_currency(user_id: int, currency: str, amount: float) -> None:
        """Пример функции продажи валюты."""
        pass
    
    @log_action(action='REGISTER')
    def example_register_user(username: str, password: str) -> int:
        """Пример функции регистрации пользователя."""
        return 1  # Возвращает user_id
    
    