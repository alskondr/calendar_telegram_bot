import datetime


def get_task_start_time(task):
    return datetime.datetime.fromisoformat(task['start'].get('dateTime', task['start'].get('date')))


def task_to_string(task, with_date=False):
    dt_format = '%d.%m.%Y %H:%M' if with_date else '%H:%M'
    return '{0} {1}'.format(get_task_start_time(task).strftime(dt_format), task['summary'])


def tasks_to_string(tasks):
    if not tasks:
        return 'Список пуст.'

    str_list = ['Расписание:']
    now = datetime.datetime.now()
    for task in tasks:
        if get_task_start_time(task).replace(tzinfo=None) < now:
            form = '_'
        else:
            form = '*'
        string = f' - {form}{task_to_string(task)}{form}'
        str_list.append(string)
    return '\n'.join(str_list)