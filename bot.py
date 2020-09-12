from configparser import ConfigParser
import random
import datetime
from threading import Thread
from time import sleep

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
        self.notify_id = None

    def __str__(self):
        return f'{self.name}: {self.dt.strftime("%d.%m.%Y %H:%M")}'


class UserData:
    def __init__(self):
        self.state = MAIN_STATE
        self.tasks = []
        self.current_task = None

    def add_current_task(self, user_id):
        if self.current_task.dt > datetime.datetime.now():
            notify_id = sender.add_notify(user_id, self.current_task)
            self.current_task.notify_id = notify_id
        self.tasks.append(self.current_task)
        self.tasks.sort(key=lambda task: task.dt)

    def remove_task(self, task_name):
        task = self.get_task(task_name)
        if task:
            sender.remove_notify(task.notify_id)
            self.tasks.remove(task)
            return True
        else:
            return False

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
    bot.send_message(user_id, 'Вас приветствует календарь бот с уведомлениями о задачах. '
                              'Вы можете создавать, удалять, просматривать задачи и получать уведомления.\n'
                              'Бот не учитывает регистр букв.\n\n'
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
    user.add_current_task(user_id)
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
    if user.remove_task(message.text.lower()):
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


class NotifySender(Thread):
    def __init__(self):
        Thread.__init__(self)
        self._notifies = {}
        self.next_id = 0

    def add_notify(self, user_id, task):
        curr_id = self.next_id
        self.next_id += 1
        self._notifies[curr_id] = [user_id, task]
        return curr_id

    def remove_notify(self, notify_id):
        if notify_id in self._notifies.keys():
            self._notifies.pop(notify_id)

    def run(self):
        while True:
            sended_notify_ids = []
            for notify_id, notify in self._notifies.items():
                delta_time = datetime.datetime.now() + datetime.timedelta(seconds=20)
                if notify[1].dt < delta_time:
                    bot.send_message(notify[0], f'Напоминание о задаче:\n{notify[1]}')
                    sended_notify_ids.append(notify_id)

            for notify_id in sended_notify_ids:
                self.remove_notify(notify_id)

            sleep(10)


sender = NotifySender()
sender.start()
bot.polling()
