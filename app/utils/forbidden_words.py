import functools
import inspect
import re

from app import config
from app.utils.exceptions import InputException


# 判断文本中是否包含禁止词（使用正则表达式实现整词匹配）
def contains_forbidden_word(text: str) -> bool:
    text_lower = text.lower()
    for word in config.forbidden_words:
        if word.lower() in text_lower:
            return True
    return False


def replace_forbidden_word(text: str) -> str:
    for word in config.forbidden_words:
        if word.lower() in text:
            text = text.replace(word, "*" * len(word))
    return text


# 带参数的装饰器
def check_params_contains_forbidden_word(*check_params):
    """
    装饰器参数check_params为需要检查禁止词的参数名列表。
    如果指定的参数中包含禁止词，则抛出ValueError异常。
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取函数签名并绑定传入的参数
            bound_args = inspect.signature(func).bind(*args, **kwargs)
            bound_args.apply_defaults()

            # 检查指定的参数
            for param in check_params:
                if param in bound_args.arguments:
                    value = bound_args.arguments[param]
                    if contains_forbidden_word(value):
                        raise InputException(f"包含禁止词")
            # 如果检查通过，则调用原函数
            return func(*args, **kwargs)

        return wrapper

    return decorator


def content_forbidden_word_filter(*contents):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # todo
            return func(*args, **kwargs)

        return wrapper

    return decorator
