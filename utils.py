#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
 Проект:            	Мониторинг общественного мнения
 Автор:             	Булдей Александр
 Связь :                https://t.me/Alex_Booldey
 Описание :             Вспомогательный модуль для скрипта сбора информации из википедии

 Версия :           	1.0
"""

import re
import sys
import time
import json
import hashlib
import pymysql

import logging.handlers

from time import time, strftime, localtime
from datetime import datetime, timedelta

time_flag = False

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.handlers.TimedRotatingFileHandler("wiki.log", when="midnight", backupCount=3)
formatter = logging.Formatter(u'LINE:[%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)


def time_util(arg):
    def outer(func):
        def wrapper(*args, **kwargs):
            start_time = time()
            result = func(*args, **kwargs)
            if arg:
                print('Func name: {0:<15} Work time {1} sec;'.format(func.__name__,
                                                                     str(round(time() - start_time, 4))))
            return result

        return wrapper

    return outer


def secondsToStr(elapsed=None):
    if elapsed is None:
        return strftime("%Y-%m-%d %H:%M:%S", localtime())
    else:
        return str(timedelta(seconds=elapsed))


def get_hash(val):
    hash_object = hashlib.md5(val.encode('utf-8'))
    return hash_object.hexdigest()


# Функция чтения конфиг файла
def load_config():
    log.info("Open file config.json")
    try:
        with open('config.json') as json_data_file:
            log.info("Read file...")
            config_json = json.load(json_data_file)
        json_data_file.close()
    except FileNotFoundError as e:
        log.critical(e)
        sys.exit(0)
    return config_json


def get_lang(val):
    try:
        return re.search(r'//(\b\w{2,6}\b)\w*', val).group(1)
    except AttributeError as e:
        log.warning('Page not support; Url: {0}'.format(val))
        return None


# util class
class SingletonMeta(type):
    def __init__(cls, name, bases, val):
        super(SingletonMeta, cls).__init__(name, bases, val)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super(SingletonMeta, cls).__call__(*args, **kw)
        return cls.instance


# database connection class
class DatabaseConnection(object):
    __metaclass__ = SingletonMeta

    # Функция инициализации соединения с базой, вызываеться автоматически при создании класса;
    # Принемает на вход json файл с конфигурационными параметрами
    def __init__(self, conf):
        self.__host = conf["mysql"]["host"]
        self.__user = conf["mysql"]["user"]
        self.__password = conf["mysql"]["password"]
        self.__database = conf["mysql"]["database"]

        pymysql.install_as_MySQLdb()
        try:
            # Получение соединения с базой
            self.__connection = pymysql.connect(host=self.__host, user=self.__user, password=self.__password,
                                                db=self.__database, charset='utf8mb4')
            # Получение курсора
            self.__cursor = self.__connection.cursor()
        except Exception as e:
            code, msg = e.args
            if code == 1049:
                log.critical(msg)
                sys.exit(0)

    def __del__(self):
        # Закрытие курсора и соединение
        self.__cursor.close()
        self.__connection.close()

    # Функция проверки существования записи в таблице
    # in - hash url
    # out - 1(True) - запись найдена
    #       0(False) - записи не найдена
    @time_util(time_flag)
    def is_exists(self, check_hash):
        try:
            self.__cursor.execute('call check_exists(%s)', check_hash)
            val = self.__cursor.fetchall()[0][0]
            self.__connection.commit()
            return val
        except Exception as e:
            log.error(e)

    # Функция сохранения статьи в базу
    # in - масив данных статьи
    # out - id последней добавленной записи
    @time_util(time_flag)
    def save_article(self, article_args):
        try:
            self.__cursor.execute("call add_article(%s,%s,%s,%s,%s,%s,%s)", article_args)
            self.__cursor.execute("call get_id(%s)", article_args[0])

            val = self.__cursor.fetchall()[0][0]
            self.__connection.commit()
            return val
        except Exception as e:
            log.error(e)

    # Функция сохранения категорий в базу
    # in parent_id - id статья к которой относятся категории
    # in category_list - список категорий
    @time_util(time_flag)
    def save_categories(self, parent_id, category_list):
        try:
            for cat in category_list:
                self.__cursor.execute("call add_article_category(%s,%s)", [parent_id, cat])
                self.__connection.commit()
        except Exception as e:
            log.error(e)

    # Функция сохранения истории в базу
    # in parent_id - id статья к которой относится история
    # in history_list - список, где
    #                   list[0] - дата и время измениния
    #                   list[1] - автор изменения
    @time_util(time_flag)
    def save_history(self, parent_id, history_list):
        try:
            for history in history_list:
                if history[0] is not None:
                    self.__cursor.execute("call add_article_history(%s,%s, %s, %s)",
                                          [parent_id, history[0], history[1], None])
                else:
                    self.__cursor.execute("call add_article_history(%s,%s, %s, %s)",
                                          [parent_id, None, history[1], history[2]])
                self.__connection.commit()
        except Exception as e:
            log.error(e)


# date formatter for mysql
class DateFormatter:

    def __init__(self):

        self.lang_support_default = {'en', 'ru', 'de', 'pl', 'ua', 'it', 'be', 'bg', 'eo', 'es', 'fr', 'simple'}
        self.__months = {
            ('января', 'януари', 'січня', 'студзень', 'Jan', 'January', 'janvier', 'sty', 'ene', 'gen'): 1,
            ('февраля', 'февруари', 'лютого', 'лютага', 'Feb', 'February', 'février', 'lut', 'feb'): 2,
            ('марта', 'март', 'березня', 'сакавіка', 'Mär', 'March', 'mars', 'mar'): 3,
            ('апреля', 'април', 'квітня', 'красавіка', 'Apr', 'April', 'avril', 'kwi', 'abr', 'apr'): 4,
            ('мая', 'май', 'травня', 'мая', 'Mai', 'May', 'mai', 'maj', 'may', 'mag'): 5,
            ('июня', 'юни', 'червня', 'чэрвеня', 'Jun', 'June', 'juin', 'cze', 'jun', 'giu'): 6,
            ('июля', 'юли', 'липня', 'ліпеня', 'Jul', 'July', 'juillet', 'lip', 'jul', 'lug'): 7,
            ('августа', 'август', 'серпня', 'жніўня', 'Aug', 'August', 'août', 'sie', 'ago'): 8,
            ('сентября', 'септември', 'вересня', 'верасня', 'Sep', 'September', 'septembre', 'wrz', 'sep', 'set'): 9,
            ('октября', 'октомври', 'жовтня', 'кастрычніка', 'Okt', 'October', 'octobre', 'paź', 'oct', 'ott'): 10,
            ('ноября', 'ноември', 'листопада', 'лістапада', 'Nov', 'November', 'novembre', 'lis', 'nov'): 11,
            ('декабря', 'декември', 'грудня', 'снежня', 'Dez', 'December', 'décembre', 'gru', 'dic'): 12}

    def __format_month(self, month):
        return next(val for k, val in self.__months.items() if month in k)

    @staticmethod
    def __clean_date(val):
        return re.sub(r'[.,]', ' ', val)

    def __format_date(self, date, lang):
        if lang == 'fr':
            clean_val = self.__clean_date(date).split()
            return '{0} {1} {2} {3}'.format(clean_val[4], clean_val[0], self.__format_month(clean_val[1]), clean_val[2])
        else:
            clean_val = self.__clean_date(date).split()
            return '{0} {1} {2} {3}'.format(clean_val[0], clean_val[1], self.__format_month(clean_val[2]), clean_val[3])

    def convert_date(self, lang, date):
        val = self.__format_date(date, lang)
        return datetime.strptime(val, '%H:%M %d %m %Y')
