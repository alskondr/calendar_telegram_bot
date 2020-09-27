import datetime
import dateutil.parser
from dateutil.tz import gettz


def get_task_start_time(task):
    return dateutil.parser.parse(task['start'].get('dateTime', task['start'].get('date')))


def get_task_start_time_utc(task):
    dt_with_tz = get_task_start_time(task)
    return dt_with_tz.astimezone(datetime.timezone.utc)


def get_task_start_time_tz(task, tz_name):
    dt_with_tz = get_task_start_time(task)
    return dt_with_tz.astimezone(gettz(tz_name))


def task_to_string(task, tz_name, with_date=False):
    dt_format = '%d.%m.%Y %H:%M' if with_date else '%H:%M'
    return '{0} {1}'.format(get_task_start_time_tz(task, tz_name).strftime(dt_format), task['summary'])


def tasks_to_string(tasks, tz_name):
    if not tasks:
        return 'Список пуст.'

    str_list = ['Расписание:']
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    for task in tasks:
        if get_task_start_time_utc(task) < now:
            form = '_'
        else:
            form = '*'
        string = f' - {form}{task_to_string(task, tz_name)}{form}'
        str_list.append(string)
    return '\n'.join(str_list)