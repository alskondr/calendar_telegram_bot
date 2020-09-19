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

# Телеграм-бот
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
    bot.send_message(user.user_id, 'Вас приветствует календарь бот, работающий с Google Календарем. '
                                   'Вы можете создавать, удалять, просматривать задачи и получать уведомления.\n\n'
                                   'Команда /auth - авторизация в Google Календаре\n'
                                   'Команда /add - добавление задачу\n'
                                   'Команда /delete - удаление задачу\n'
                                   'Команда /tasks - список задач\n'
                                   'Команда /help - данная справка')
    user.state = states.MAIN_STATE


@bot.message_handler(commands=['auth'])
def auth_handler(message):
    user = get_user_data(message.from_user.id)
    bot.send_message(user.user_id,
                     'Для авторизации в Google аккаунте и '
                     'предоставления доступа боту к Вашему календарю пройдите по [ссылке]({0}).\n'
                     'После авторизации отправьте боту полученный код.'.format(AUTHORIZATION_URL),
                     parse_mode="MARKDOWN")
    user.state = states.AUTHORIZATION_STATE


def authorization_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)

    code = message.text
    if not user.init_service(code):
        bot.reply_to(message, 'Неверный код авторизации!!!\n'
                              'Введите код, скопированный из авторизационной формы Google.')
    else:
        bot.reply_to(message, 'Авторизация прошла успешно. '
                              'Теперь Вы можете взаимодействовать со своим Google Календарем.')
        user.state = states.MAIN_STATE

#
# @bot.message_handler(commands=['add'])
# def add_handler(message):
#     user_id = message.from_user.id
#     bot.send_message(user_id, 'Добавление задачи. Введите имя.')
#     get_user_data(user_id).state = ENTER_ADDED_TASK_NAME_STATE
#
#
# def enter_added_task_name_handler(message):
#     user_id = message.from_user.id
#     user = get_user_data(user_id)
#     task_name = message.text.lower()
#     if user.get_task(task_name):
#         bot.reply_to(message, 'Эта задача уже существует. Введите новое название.')
#     else:
#         user.current_task = Task(task_name)
#         markup = keyboard.create_date_time_widget(datetime.datetime.now())
#         bot.send_message(message.from_user.id, 'Введите дату и время начала задачи.', reply_markup=markup)
#         user.state = ENTER_ADDED_TASK_DATE_STATE


@bot.callback_query_handler(func=lambda call: call)
def markup_handler(call):
    dt = keyboard.keyboard_handler(bot, call)
    if dt:
        user_id = call.message.chat.id
        user = get_user_data(user_id)

        if user.state == states.TASKS_STATE:
            tasks = user.get_day_tasks(dt.date())
            bot.edit_message_text(taskutils.tasks_to_string(tasks),
                                  user_id,
                                  call.message.message_id,
                                  parse_mode='MARKDOWN')
            user.state = states.MAIN_STATE

        # user_id = call.message.chat.id
        # user = get_user_data(user_id)
        # user.current_task.dt = dt
        # user.add_current_task(user_id)
        # bot.send_message(chat_id=user_id,
        #                  text=f'Задача *{user.current_task}* добавлена в список.',
        #                  parse_mode='MARKDOWN')
        # user.state = MAIN_STATE


# @bot.message_handler(commands=['delete'])
# def delete_handler(message):
#     user_id = message.from_user.id
#     bot.send_message(user_id, 'Удаление задачи. Введите имя.')
#     get_user_data(user_id).state = DELETE_TASK_STATE
#
#
# def delete_task_handler(message):
#     user_id = message.from_user.id
#     user = get_user_data(user_id)
#     if user.remove_task(message.text.lower()):
#         bot.reply_to(message, 'Задача успешно удалена.')
#         user.state = MAIN_STATE
#     else:
#         bot.reply_to(message, 'Эта задача отсутствует в списке. Введите другое название.')


@bot.message_handler(commands=['tasks'])
def tasks_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    markup = keyboard.create_calendar(datetime.datetime.now(), True)
    bot.send_message(user_id, 'Укажите дату:', reply_markup=markup)
    user.state = states.TASKS_STATE


# def enter_print_tasks_date_handler(message):
#     user_id = message.from_user.id
#     user = get_user_data(user_id)
#     date_string = message.text.lower()
#
#     if date_string == 'все':
#         output_message = tasks_to_string(user.tasks)
#     elif date_string == 'сегодня':
#         output_message = tasks_to_string(user.get_day_tasks(datetime.date.today()))
#     elif date_string == 'завтра':
#         output_message = tasks_to_string(user.get_day_tasks(datetime.date.today() + datetime.timedelta(days=1)))
#     else:
#         try:
#             dt = datetime.datetime.strptime(date_string, "%d.%m.%Y")
#         except ValueError:
#             bot.reply_to(message, 'Время введено в неверном формате. '
#                                   'Попробуйте еще раз в формате "дд.мм.гггг", или "все", или "сегодня", или "завтра".')
#             return
#
#         output_message = tasks_to_string(user.get_day_tasks(dt.date()))
#
#     bot.send_message(user_id, output_message)
#     user.state = MAIN_STATE
#
#
# def tasks_to_string(tasks):
#     if not tasks:
#         output_message = 'Список пуст'
#     else:
#         output_message = 'Задачи:'
#         for task in tasks:
#             output_message += f'\n - {task}'
#     return output_message
#
#
# def random_task_handler(message):
#     user_id = message.from_user.id
#     user = get_user_data(user_id)
#     output_message = f'Хватит дурачиться, займись делом.'
#     future_tasks = user.get_future_tasks()
#     if future_tasks:
#         task = random.choice(future_tasks)
#         output_message += f'\nНапример, {task}'
#
#     bot.send_message(user_id, output_message)
#     user.state = MAIN_STATE


@bot.message_handler(func=lambda message: True)
def dispatcher(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    state = user.state

    if state == states.AUTHORIZATION_STATE:
        authorization_handler(message)

    # if state == ENTER_ADDED_TASK_NAME_STATE:
    #     enter_added_task_name_handler(message)
    # elif state == DELETE_TASK_STATE:
    #     delete_task_handler(message)
    # elif state == RANDOM_TASK_STATE:
    #     random_task_handler(message)
    # elif state == ENTER_PRINT_TASKS_DATE_STATE:
    #     enter_print_tasks_date_handler(message)
    # else:
    #     bot.send_message(user_id, 'Не понял, повтори...')
    #     user.state = RANDOM_TASK_STATE


sender = NotifySender(bot, data)
sender.start()
bot.polling()
