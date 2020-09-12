import configparser
import random

import telebot

MAIN_STATE = 0
ADD_TASK_STATE = 1
DELETE_TASK_STATE = 2
FREE_STATE = 3

config = configparser.ConfigParser()
config.read("settings.ini")
try:
    token = config['telegram']['token']
except KeyError:
    print('Не указан токен телеграм бота в конфигурационном файле')
    exit(-1)

bot = telebot.TeleBot(token)


class UserData:
    def __init__(self):
        self.state = MAIN_STATE
        self.tasks = []


data = {}


def get_user_data(user_id):
    if user_id not in data:
        user = UserData()
        data[user_id] = user
        return user
    else:
        return data[user_id]


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    get_user_data(user_id)
    bot.send_message(user_id, 'Вас приветствует календарь бот, который хранит список задач. '
                              'Задачи хранятся в нижнем регистре.\n\n'
                              'Команда /add - добавляет задачу\n'
                              'Команда /delete - удаляет задачу\n'
                              'Команда /tasks - список задач\n'
                              'Команда /help - данная справка')


@bot.message_handler(commands=['add'])
def add_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Добавление задачи. Введите имя.')
    get_user_data(user_id).state = ADD_TASK_STATE


@bot.message_handler(commands=['delete'])
def delete_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Удаление задачи. Введите имя.')
    get_user_data(user_id).state = DELETE_TASK_STATE


@bot.message_handler(commands=['tasks'])
def tasks_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)

    if not user.tasks:
        output_message = 'Список пуст'
    else:
        output_message = 'Задачи:'
        for task in user.tasks:
            output_message += '\n - ' + task

    bot.send_message(user_id, output_message)
    user.state = MAIN_STATE


def add_task(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    task = message.text.lower()
    if task in user.tasks:
        bot.reply_to(message, 'Эта задача уже существует. Введите новое название.')
    else:
        user.tasks.append(task)
        bot.reply_to(message, 'Задача добавлена в список.')
        user.state = MAIN_STATE


def delete_task(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    task = message.text.lower()
    if task in user.tasks:
        user.tasks.remove(task)
        bot.reply_to(message, 'Задача успешно удалена.')
        user.state = MAIN_STATE
    else:
        bot.reply_to(message, 'Эта задача отсутствует в списке. Введите другое название.')


def random_task(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    output_message = f'Хватит дурачиться, займись делом.'
    if user.tasks:
        task = random.choice(user.tasks)
        output_message += f'\nНапример, {task}'

    bot.send_message(user_id, output_message)
    user.state = MAIN_STATE


@bot.message_handler(func=lambda message: True)
def dispatcher(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    state = user.state
    
    if state == ADD_TASK_STATE:
        add_task(message)
    elif state == DELETE_TASK_STATE:
        delete_task(message)
    elif state == FREE_STATE:
        random_task(message)
    else:
        bot.send_message(user_id, 'Не понял, повтори...')
        user.state = FREE_STATE


bot.polling()
