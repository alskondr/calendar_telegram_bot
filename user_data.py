import pickle
import datetime
from dateutil.tz import gettz
import os
from pathlib import Path

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

import states
import taskutils


# Путь к директории с конфигурационными файлами
CONFIG_PATH = os.path.join(Path.home(), '.config', 'calendar_telegram_bot')
os.makedirs(CONFIG_PATH, exist_ok=True)


# Путь к директории с параметрами авторизации пользователей
DATA_PATH = os.path.join(Path.home(), '.local', 'share', 'calendar_telegram_bot')
os.makedirs(DATA_PATH, exist_ok=True)


# Служба авторизации в google
SCOPES = ['https://www.googleapis.com/auth/calendar']
flow = Flow.from_client_secrets_file(os.path.join(CONFIG_PATH, 'client_id.json'),
                                     SCOPES,
                                     redirect_uri='urn:ietf:wg:oauth:2.0:oob')
AUTHORIZATION_URL, _ = flow.authorization_url(prompt='consent')


class UserData:
    def __init__(self, user_id):
        self.user_id = user_id
        self.state = states.MAIN_STATE
        self.service = None
        # self.current_task = None

        credentials_path = self.get_credentials_path()
        if os.path.exists(credentials_path):
            with open(credentials_path, 'rb') as token:
                credentials = pickle.load(token)
                if not credentials.valid and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                if credentials.valid:
                    self.service = build('calendar', 'v3', credentials=credentials)

    def get_credentials_path(self):
        return os.path.join(DATA_PATH, '.'.join([str(self.user_id), 'token', 'pickle']))

    def init_service(self, authorization_code):
        try:
            flow.fetch_token(code=authorization_code)
        except InvalidGrantError:
            return False

        credentials = flow.credentials
        self.service = build('calendar', 'v3', credentials=credentials)
        with open(self.get_credentials_path(), 'wb') as token:
            pickle.dump(credentials, token)
        return True

    # def add_current_task(self, user_id):
    #     if self.current_task.dt > datetime.datetime.now():
    #         notify_id = sender.add_notify(user_id, self.current_task)
    #         self.current_task.notify_id = notify_id
    #     self.tasks.append(self.current_task)
    #     self.tasks.sort(key=lambda task: task.dt)
    #
    # def remove_task(self, task_name):
    #     task = self.get_task(task_name)
    #     if task:
    #         sender.remove_notify(task.notify_id)
    #         self.tasks.remove(task)
    #         return True
    #     else:
    #         return False

    def get_calendars(self):
        calendars = self.service.calendarList().list().execute()
        return calendars.get('items', [])

    def get_tasks(self, min_date_time, max_date_time):
        day_tasks = []
        for calendar in self.get_calendars():
            tz = gettz(calendar.get('timeZone', 'UTC'))
            time_min = min_date_time.replace(tzinfo=tz).isoformat()
            time_max = max_date_time.replace(tzinfo=tz).isoformat()
            tasks = self.service.events().list(calendarId=calendar['id'],
                                               timeMin=time_min,
                                               timeMax=time_max,
                                               singleEvents=True,
                                               orderBy='startTime').execute()
            day_tasks.extend(tasks.get('items', []))
        day_tasks.sort(key=lambda task: taskutils.get_task_start_time(task))
        return day_tasks

    def get_day_tasks(self, date):
        dt_min = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
        dt_max = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)
        return self.get_tasks(dt_min, dt_max)

    def get_future_tasks(self):
        future_tasks = []
        now = datetime.datetime.utcnow()
        for calendar in self.get_calendars():
            tasks = self.service.events().list(calendarId=calendar['id'],
                                               timeMin=now,
                                               maxResults=5,
                                               singleEvents=True,
                                               orderBy='startTime').execute()
            future_tasks.extend(tasks.get('items', []))
        future_tasks.sort(key=lambda task: taskutils.get_task_start_time(task))
        return future_tasks