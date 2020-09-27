from threading import Thread
import datetime
from time import sleep

import taskutils


class NotifySender(Thread):
    SLEEP_TIMEOUT = 10

    def __init__(self, bot, data):
        Thread.__init__(self)
        self._last_time = None
        self._bot = bot
        self._data = data

    def run(self):
        self._last_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        while True:
            current_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) + \
                           datetime.timedelta(seconds=self.SLEEP_TIMEOUT)
            for user in self._data.values():
                if not user.service:
                    continue
                tasks = user.get_tasks(self._last_time, current_time)
                for task in tasks:
                    if self._last_time < taskutils.get_task_start_time_utc(task) < current_time:
                        self._bot.send_message(user.user_id,
                                               f'Напоминание о задаче:\n*{taskutils.task_to_string(task, user.tz_name)}*',
                                               parse_mode='MARKDOWN')
            self._last_time = current_time
            sleep(self.SLEEP_TIMEOUT)
