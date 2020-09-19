import datetime
import calendar
import json

from dateutil.relativedelta import relativedelta

DT_FORMAT = '%Y.%m.%d.%H.%M'


def keyboard_handler(bot, call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    calendar_data = call.data.split(':')

    if not calendar_data:
        pass
    elif calendar_data[0] == 'dt':
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
        return datetime.datetime.strptime(calendar_data[1], DT_FORMAT)
    elif calendar_data[0] == 'calendar':
        dt = datetime.datetime.strptime(calendar_data[1], DT_FORMAT)
        markup = create_calendar(dt, False)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
    elif calendar_data[0] == 'calendar_day':
        dt = datetime.datetime.strptime(calendar_data[1], DT_FORMAT)
        if calendar_data[2]:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
            return dt
        else:
            markup = create_date_time_widget(dt)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
    elif calendar_data[0] == 'calendar_month':
        option = calendar_data[1]
        dt = datetime.datetime.strptime(calendar_data[2], DT_FORMAT)
        if option == 'prev':
            dt -= relativedelta(months=1)
        elif option == 'next':
            dt += relativedelta(months=1)
        markup = create_calendar(dt, calendar_data[3])
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
    elif calendar_data[0] == 'today':
        dt = datetime.datetime.strptime(calendar_data[1], DT_FORMAT)
        now = datetime.date.today()
        dt = dt.replace(year=now.year, month=now.month, day=now.day)
        if calendar_data[2]:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
            return dt
        else:
            markup = create_date_time_widget(dt)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
    elif calendar_data[0] == 'tomorrow':
        dt = datetime.datetime.strptime(calendar_data[1], DT_FORMAT)
        now = datetime.date.today() + datetime.timedelta(days=1)
        dt = dt.replace(year=now.year, month=now.month, day=now.day)
        if calendar_data[2]:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
            return dt
        else:
            markup = create_date_time_widget(dt)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
    elif calendar_data[0] == 'edit':
        state = calendar_data[1]
        option = calendar_data[2]
        dt = datetime.datetime.strptime(calendar_data[3], DT_FORMAT)
        if option == 'prev':
            if state == 'year':
                dt -= relativedelta(years=1)
            elif state == 'month':
                dt -= relativedelta(months=1)
            elif state == 'day':
                dt -= relativedelta(days=1)
            elif state == 'hour':
                dt -= relativedelta(hours=1)
            elif state == 'minute':
                dt -= relativedelta(minutes=1)
        elif option == 'next':
            if state == 'year':
                dt += relativedelta(years=1)
            elif state == 'month':
                dt += relativedelta(months=1)
            elif state == 'day':
                dt += relativedelta(days=1)
            elif state == 'hour':
                dt += relativedelta(hours=1)
            elif state == 'minute':
                dt += relativedelta(minutes=1)
        markup = create_date_time_widget(dt)
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
    elif calendar_data[0] == 'empty':
        bot.answer_callback_query(call.id)

    return None


def create_callback_data(*args):
    return ':'.join(str(arg) for arg in args)


def create_calendar(dt, only_calendar=True):
    empty_callback_data = create_callback_data('empty')
    markup = {'inline_keyboard': []}

    # Год, месяц
    row = [{'text': f'{calendar.month_name[dt.month]} {str(dt.year)}', 'callback_data': empty_callback_data}]
    markup['inline_keyboard'].append(row)

    # Дни недели
    row = []
    for day in calendar.day_abbr:
        row.append({'text': day, 'callback_data': empty_callback_data})
    markup['inline_keyboard'].append(row)

    # Календарь
    month_calendar = calendar.monthcalendar(dt.year, dt.month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append({'text': ' ', 'callback_data': empty_callback_data})
            else:
                dt = dt.replace(day=day)
                row.append({'text': str(day), 'callback_data': create_callback_data('calendar_day',
                                                                                    dt.strftime(DT_FORMAT),
                                                                                    only_calendar)})
        markup['inline_keyboard'].append(row)

    # Кнопки переключения
    row = [{'text': '<', 'callback_data': create_callback_data('calendar_month',
                                                               'prev',
                                                               dt.strftime(DT_FORMAT),
                                                               only_calendar)},
           {'text': '>', 'callback_data': create_callback_data('calendar_month',
                                                               'next',
                                                               dt.strftime(DT_FORMAT),
                                                               only_calendar)}]
    markup['inline_keyboard'].append(row)

    # Сегодня, завтра
    row = [{'text': 'Сегодня', 'callback_data': create_callback_data('today',
                                                                     dt.strftime(DT_FORMAT),
                                                                     only_calendar)},
           {'text': 'Завтра', 'callback_data': create_callback_data('tomorrow',
                                                                    dt.strftime(DT_FORMAT),
                                                                    only_calendar)}]
    markup['inline_keyboard'].append(row)

    return json.dumps(markup)


def create_date_time_widget(dt):
    markup = {'inline_keyboard': []}
    params = ['day', 'month', 'year', 'hour', 'minute']
    dt_str = dt.strftime(DT_FORMAT)
    empty_callback_data = create_callback_data('empty')

    # Заголовки
    headers = ['День', 'Месяц', 'Год', 'Час', 'Минута']
    row = [{'text': header, 'callback_data': empty_callback_data} for header in headers]
    markup['inline_keyboard'].append(row)

    # Инкремент
    row = [{'text': '▲', 'callback_data': create_callback_data('edit', param, 'next', dt_str)} for param in params]
    markup['inline_keyboard'].append(row)

    # Дата, время
    row = [{'text': str(dt.day), 'callback_data': empty_callback_data},
           {'text': str(dt.month), 'callback_data': empty_callback_data},
           {'text': str(dt.year), 'callback_data': empty_callback_data},
           {'text': str(dt.hour), 'callback_data': empty_callback_data},
           {'text': str(dt.minute), 'callback_data': empty_callback_data}]
    markup['inline_keyboard'].append(row)

    # Декремент
    row = [{'text': '▼', 'callback_data': create_callback_data('edit', param, 'prev', dt_str)} for param in params]
    markup['inline_keyboard'].append(row)

    # Календарь
    row = [{'text': 'Календарь', 'callback_data': create_callback_data('calendar', dt_str)}]
    markup['inline_keyboard'].append(row)

    # Готово
    row = [{'text': 'Готово', 'callback_data': create_callback_data('dt', dt_str)}]
    markup['inline_keyboard'].append(row)

    return json.dumps(markup)
