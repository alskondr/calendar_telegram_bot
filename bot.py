from configparser import ConfigParser
import random
import datetime
import os.path

import telebot

import keyboard
import taskutils
import states
from notify_sender import NotifySender
from user_data import UserData, AUTHORIZATION_URL, CONFIG_PATH


config = ConfigParser()
config.read(os.path.join(CONFIG_PATH, 'settings.ini'))
try:
    telegram_token = config['telegram']['token']
except KeyError:
    print('Не указан токен телеграм бота в конфигурационном файле')
    exit(-1)


bot = telebot.TeleBot(telegram_token)


data = {}


def get_user_data(user_id):
    if user_id not in data:
        user = UserData(user_id)
        data[user_id] = user
        return user
    else:
        return data[user_id]


@bot.message_handler(commands=['start', 'help'])
def start_handler(message):
    user = get_user_data(message.from_user.id)
    auth_message = '\n\n*Вы не авторизованы в Google аккаунте.*' if not user.service else ''
    bot.send_message(user.user_id,
                     'Вас приветствует календарь бот, работающий с Google Календарем. '
                     'Вы можете создавать, удалять, просматривать задачи и получать уведомления.\n\n'
                     'Команда /auth - авторизация в Google Календаре\n'
                     'Команда /add - добавление задачу\n'
                     'Команда /delete - удаление задачу\n'
                     'Команда /tasks - список задач\n'
                     'Команда /help - данная справка{0}'.format(auth_message),
                     parse_mode='MARKDOWN')
    user.state = states.MAIN_STATE


def no_auth_handler(message):
    user = get_user_data(message.from_user.id)
    bot.send_message(message.from_user.id,
                     '*Вы не авторизованы в Google аккаунте.*\n'
                     'Авторизация: /auth',
                     parse_mode='MARKDOWN')
    user.state = states.MAIN_STATE


@bot.message_handler(commands=['auth'])
def auth_handler(message):
    user = get_user_data(message.from_user.id)
    if not user.service:
        bot.send_message(user.user_id,
                         'Для авторизации в Google аккаунте и '
                         'предоставления доступа боту к Вашему календарю пройдите по [ссылке]({0}).\n\n'
                         'После авторизации отправьте боту полученный код.'.format(AUTHORIZATION_URL),
                         parse_mode="MARKDOWN")
    else:
        bot.send_message(user.user_id,
                         '*Вы уже авторизированы в Google аккаунте.*\n\n'
                         'Для смены пользователя пройдите по [ссылке]({0}).\n\n'
                         'После авторизации отправьте боту полученный код.'.format(AUTHORIZATION_URL),
                         parse_mode="MARKDOWN")
    user.state = states.AUTHORIZATION_STATE


def authorization_handler(message):
    user = get_user_data(message.from_user.id)

    code = message.text
    if not user.init_service(code):
        bot.reply_to(message, 'Неверный код авторизации!!!\n'
                              'Введите код, скопированный из авторизационной формы Google.')
    else:
        bot.reply_to(message, 'Авторизация прошла успешно. '
                              'Теперь Вы можете взаимодействовать со своим Google Календарем.')
        user.state = states.MAIN_STATE


@bot.message_handler(commands=['add'])
def add_handler(message):
    user = get_user_data(message.from_user.id)
    if not user.service:
        no_auth_handler(message)
        return
    bot.send_message(user.user_id, 'Добавление задачи. Введите имя.')
    user.state = states.ENTER_ADDED_TASK_NAME_STATE


def enter_added_task_name_handler(message):
    user = get_user_data(message.from_user.id)
    user.current_task_name = message.text
    markup = keyboard.create_date_time_widget(datetime.datetime.now())
    bot.send_message(message.from_user.id, 'Введите дату и время начала задачи.', reply_markup=markup)
    user.state = states.ENTER_ADDED_TASK_DATE_STATE


@bot.message_handler(commands=['delete'])
def delete_handler(message):
    user = get_user_data(message.from_user.id)
    if not user.service:
        no_auth_handler(message)
        return
    markup = keyboard.create_calendar(datetime.datetime.now(), True)
    bot.send_message(user.user_id, 'Укажите дату:', reply_markup=markup)
    user.state = states.DELETE_TASK_STATE


@bot.message_handler(commands=['tasks'])
def tasks_handler(message):
    user = get_user_data(message.from_user.id)
    if not user.service:
        no_auth_handler(message)
        return

    markup = keyboard.create_calendar(datetime.datetime.now(), True)
    bot.send_message(user.user_id, 'Укажите дату:', reply_markup=markup)
    user.state = states.TASKS_STATE


def random_task_handler(message):
    user = get_user_data(message.from_user.id)
    output_message = f'Хватит дурачиться, займись делом.'
    future_tasks = user.get_future_tasks()
    if future_tasks:
        task = random.choice(future_tasks)
        output_message += f'\nНапример, {taskutils.task_to_string(task, with_date=True)}'

    bot.send_message(user.user_id, output_message)
    user.state = states.MAIN_STATE


@bot.message_handler(func=lambda message: True)
def dispatcher(message):
    user = get_user_data(message.from_user.id)
    state = user.state

    if state == states.AUTHORIZATION_STATE:
        authorization_handler(message)
    elif state == states.ENTER_ADDED_TASK_NAME_STATE:
        enter_added_task_name_handler(message)
    elif state == states.RANDOM_TASK_STATE:
        random_task_handler(message)
    else:
        if not user.service:
            no_auth_handler(message)
            return
        bot.send_message(user.user_id, 'Не понял, повтори...')
        user.state = states.RANDOM_TASK_STATE


@bot.callback_query_handler(func=lambda call: call)
def markup_handler(call):
    user = get_user_data(call.message.chat.id)

    if user.state == states.DELETE_TASK_SUCCESS_STATE:
        tasks_data = call.data.split(':')
        user.remove_task(tasks_data[1])
        bot.edit_message_text('Задача удалена.', user.user_id, call.message.message_id)
        user.state = states.MAIN_STATE
        return

    dt = keyboard.keyboard_handler(bot, call)
    if dt:
        if user.state == states.TASKS_STATE:
            tasks = user.get_day_tasks(dt.date())
            bot.edit_message_text(taskutils.tasks_to_string(tasks),
                                  user.user_id,
                                  call.message.message_id,
                                  parse_mode='MARKDOWN')
            user.state = states.MAIN_STATE
        elif user.state == states.ENTER_ADDED_TASK_DATE_STATE:
            user.add_task(user.current_task_name, dt)
            bot.edit_message_text('Задача *{0} {1}* добавлена в список.'.format(dt.strftime('%d.%m.%Y %H:%M'),
                                                                                user.current_task_name),
                                  user.user_id,
                                  call.message.message_id,
                                  parse_mode='MARKDOWN')
            user.state = states.MAIN_STATE
        elif user.state == states.DELETE_TASK_STATE:
            tasks = user.get_day_tasks(dt.date())
            if not tasks:
                bot.edit_message_text('Задач на выбранную дату нет.', user.user_id, call.message.message_id)
            markup = keyboard.create_tasks_list(tasks)
            bot.edit_message_text('Выберите задачу для удаления:',
                                  user.user_id,
                                  call.message.message_id,
                                  reply_markup=markup)
            user.state = states.DELETE_TASK_SUCCESS_STATE


sender = NotifySender(bot, data)
sender.start()
bot.polling()
