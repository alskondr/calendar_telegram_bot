import pickle
import datetime
from dateutil.tz import gettz, tzlocal
import os
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
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
        self.current_task_name = ''
        self._calendar_id = ''

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

    def _get_calendar_id(self):
        try:
            self.service.calendars().get(calendarId=self._calendar_id).execute()
        except HttpError:
            self._calendar_id = ''
            for calendar in self.get_calendars():
                if calendar['summary'] == 'kas_calendar_bot':
                    self._calendar_id = calendar['id']
                    break
            if not self._calendar_id:
                calendar_dict = {
                    'summary': 'kas_calendar_bot',
                    'timeZone': 'Europe/Moscow'
                }
                created_calendar = self.service.calendars().insert(body=calendar_dict).execute()
                self._calendar_id = created_calendar['id']
        return self._calendar_id

    def add_task(self, task_name, dt):
        calendar_id = self._get_calendar_id()
        event = {
            'summary': task_name,
            'start': {
                'dateTime': dt.replace(tzinfo=tzlocal()).isoformat()
            },
            'end': {
                'dateTime': (dt.replace(tzinfo=tzlocal()) + datetime.timedelta(hours=1)).isoformat()
            }
        }
        self.service.events().insert(calendarId=calendar_id, body=event).execute()

    def remove_task(self, task_id):
        for calendar in self.get_calendars():
            try:
                self.service.events().get(calendarId=calendar['id'], eventId=task_id).execute()
            except HttpError:
                continue
            self.service.events().delete(calendarId=calendar['id'], eventId=task_id).execute()

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
        now = datetime.datetime.now()
        for calendar in self.get_calendars():
            tz = gettz(calendar.get('timeZone', 'UTC'))
            now_str = now.replace(tzinfo=tz).isoformat()
            tasks = self.service.events().list(calendarId=calendar['id'],
                                               timeMin=now_str,
                                               maxResults=5,
                                               singleEvents=True,
                                               orderBy='startTime').execute()
            future_tasks.extend(tasks.get('items', []))
        return future_tasks
