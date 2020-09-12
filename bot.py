from configparser import ConfigParser
import random
import datetime

import telebot

MAIN_STATE = 0
ENTER_ADDED_TASK_NAME_STATE = 1
ENTER_ADDED_TASK_DATE_STATE = 2
DELETE_TASK_STATE = 3
RANDOM_TASK_STATE = 4
ENTER_PRINT_TASKS_DATE_STATE = 5

config = ConfigParser()
config.read("settings.ini")
try:
    token = config['telegram']['token']
except KeyError:
    print('Не указан токен телеграм бота в конфигурационном файле')
    exit(-1)

bot = telebot.TeleBot(token)


class Task:
    def __init__(self, task_name):
        self.name = task_name
        self.dt = None

    def __str__(self):
        return f'{self.name}: {self.dt.strftime("%d.%m.%Y %H:%M")}'


class UserData:
    def __init__(self):
        self.state = MAIN_STATE
        self.tasks = []
        self.current_task = None

    def get_task(self, task_name):
        for task in self.tasks:
            if task.name == task_name:
                return task
        return None

    def get_day_tasks(self, date):
        day_tasks = []
        # Будем искать с конца, чтобы при большом количестве задач поиск был быстрее
        for task in reversed(self.tasks):
            if task.dt.date() == date:
                day_tasks.insert(0, task)
            elif task.dt.date() < date:
                break
        return day_tasks

    def get_future_tasks(self):
        future_tasks = []
        now_time = datetime.datetime.now()
        for task in reversed(self.tasks):
            if task.dt >= now_time:
                future_tasks.insert(0, task)
            else:
                break
        return future_tasks


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
    get_user_data(user_id).state = ENTER_ADDED_TASK_NAME_STATE


def enter_added_task_name_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    task_name = message.text.lower()
    if user.get_task(task_name):
        bot.reply_to(message, 'Эта задача уже существует. Введите новое название.')
    else:
        user.current_task = Task(task_name)
        bot.reply_to(message, 'Введите дату и время начала задачи в формате "дд.мм.гггг чч:мм".')
        user.state = ENTER_ADDED_TASK_DATE_STATE


def enter_added_task_date_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)

    try:
        dt = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
    except ValueError:
        bot.reply_to(message, 'Время введено в неверном формате. Попробуйте еще раз в формате "дд.мм.гггг чч:мм".')
        return

    user.current_task.dt = dt
    user.tasks.append(user.current_task)
    user.tasks.sort(key=lambda task: task.dt)
    bot.reply_to(message, 'Задача добавлена в список.')
    user.state = MAIN_STATE


@bot.message_handler(commands=['delete'])
def delete_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Удаление задачи. Введите имя.')
    get_user_data(user_id).state = DELETE_TASK_STATE


def delete_task_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    task = user.get_task(message.text.lower())
    if task:
        user.tasks.remove(task)
        bot.reply_to(message, 'Задача успешно удалена.')
        user.state = MAIN_STATE
    else:
        bot.reply_to(message, 'Эта задача отсутствует в списке. Введите другое название.')


@bot.message_handler(commands=['tasks'])
def tasks_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    bot.send_message(user_id, 'Вывод списка задач. '
                              'Введите дату в формате "дд.мм.гггг", или "все", или "сегодня", или "завтра"')
    user.state = ENTER_PRINT_TASKS_DATE_STATE


def enter_print_tasks_date_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    date_string = message.text.lower()

    if date_string == 'все':
        output_message = tasks_to_string(user.tasks)
    elif date_string == 'сегодня':
        output_message = tasks_to_string(user.get_day_tasks(datetime.date.today()))
    elif date_string == 'завтра':
        output_message = tasks_to_string(user.get_day_tasks(datetime.date.today() + datetime.timedelta(days=1)))
    else:
        try:
            dt = datetime.datetime.strptime(date_string, "%d.%m.%Y")
        except ValueError:
            bot.reply_to(message, 'Время введено в неверном формате. '
                                  'Попробуйте еще раз в формате "дд.мм.гггг", или "все", или "сегодня", или "завтра".')
            return

        output_message = tasks_to_string(user.get_day_tasks(dt.date()))

    bot.send_message(user_id, output_message)
    user.state = MAIN_STATE


def tasks_to_string(tasks):
    if not tasks:
        output_message = 'Список пуст'
    else:
        output_message = 'Задачи:'
        for task in tasks:
            output_message += f'\n - {task}'
    return output_message


def random_task_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    output_message = f'Хватит дурачиться, займись делом.'
    future_tasks = user.get_future_tasks()
    if future_tasks:
        task = random.choice(future_tasks)
        output_message += f'\nНапример, {task}'

    bot.send_message(user_id, output_message)
    user.state = MAIN_STATE


@bot.message_handler(func=lambda message: True)
def dispatcher(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    state = user.state
    
    if state == ENTER_ADDED_TASK_NAME_STATE:
        enter_added_task_name_handler(message)
    elif state == ENTER_ADDED_TASK_DATE_STATE:
        enter_added_task_date_handler(message)
    elif state == DELETE_TASK_STATE:
        delete_task_handler(message)
    elif state == RANDOM_TASK_STATE:
        random_task_handler(message)
    elif state == ENTER_PRINT_TASKS_DATE_STATE:
        enter_print_tasks_date_handler(message)
    else:
        bot.send_message(user_id, 'Не понял, повтори...')
        user.state = RANDOM_TASK_STATE


bot.polling()
