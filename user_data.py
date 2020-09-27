import datetime
from dateutil.tz import gettz, tzlocal
import os
from threading import Lock
import json

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
import google.oauth2.credentials

import redis

import states
import taskutils


# Redis
REDIS_URL = os.environ['REDIS_URL']
redis_db = redis.from_url(REDIS_URL)


# Служба авторизации в google
SCOPES = ['https://www.googleapis.com/auth/calendar']
GOOGLE_TOKEN = os.environ['GOOGLE_TOKEN']
GOOGLE_CLIENT_CONFIG = json.loads(GOOGLE_TOKEN)
flow = Flow.from_client_config(GOOGLE_CLIENT_CONFIG,
                               SCOPES,
                               redirect_uri='urn:ietf:wg:oauth:2.0:oob')
AUTHORIZATION_URL, _ = flow.authorization_url(prompt='consent')


class UserData:
    def __init__(self, user_id):
        self.user_id = user_id
        self.state = states.MAIN_STATE
        self.service = None
        self._lock = Lock()
        self.current_task_name = ''
        self._calendar_id = ''

        redis_data = redis_db.get(f'{user_id}_data')
        if redis_data:
            d = json.loads(redis_data)
            self.state = int(d['state'])
            self.current_task_name = d['task']
            self._calendar_id = d['calendar']

        redis_token = redis_db.get(f'{user_id}_token')
        if redis_token:
            credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(json.loads(redis_token))
            credentials.refresh(Request())
            if credentials.valid:
                self.service = build('calendar', 'v3', credentials=credentials)

    def set_state(self, state):
        self.state = state
        self.dumps_to_redis()

    def set_current_task_name(self, task_name):
        self.current_task_name = task_name
        self.dumps_to_redis()

    def init_service(self, authorization_code):
        try:
            flow.fetch_token(code=authorization_code)
        except InvalidGrantError:
            return False

        credentials = flow.credentials
        self.service = build('calendar', 'v3', credentials=credentials)
        redis_db.set(f'{self.user_id}_token', credentials.to_json())
        return True

    def _get_calendar_id(self):
        self._lock.acquire()
        try:
            self.service.calendars().get(calendarId=self._calendar_id).execute()
        except HttpError:
            self._lock.release()
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
                self._lock.acquire()
                created_calendar = self.service.calendars().insert(body=calendar_dict).execute()
                self._lock.release()
                self._calendar_id = created_calendar['id']
        else:
            self._lock.release()
        self.dumps_to_redis()
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
        self._lock.acquire()
        self.service.events().insert(calendarId=calendar_id, body=event).execute()
        self._lock.release()

    def remove_task(self, task_id):
        for calendar in self.get_calendars():
            self._lock.acquire()
            try:
                self.service.events().get(calendarId=calendar['id'], eventId=task_id).execute()
            except HttpError:
                continue
            finally:
                self._lock.release()
            self._lock.acquire()
            self.service.events().delete(calendarId=calendar['id'], eventId=task_id).execute()
            self._lock.release()

    def get_calendars(self):
        self._lock.acquire()
        calendars = self.service.calendarList().list().execute()
        self._lock.release()
        return calendars.get('items', [])

    def get_tasks(self, min_date_time, max_date_time):
        day_tasks = []
        for calendar in self.get_calendars():
            tz = gettz(calendar.get('timeZone', 'UTC'))
            time_min = min_date_time.replace(tzinfo=tz).isoformat()
            time_max = max_date_time.replace(tzinfo=tz).isoformat()
            self._lock.acquire()
            tasks = self.service.events().list(calendarId=calendar['id'],
                                               timeMin=time_min,
                                               timeMax=time_max,
                                               singleEvents=True,
                                               orderBy='startTime').execute()
            self._lock.release()
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
            self._lock.acquire()
            tasks = self.service.events().list(calendarId=calendar['id'],
                                               timeMin=now_str,
                                               maxResults=5,
                                               singleEvents=True,
                                               orderBy='startTime').execute()
            self._lock.release()
            future_tasks.extend(tasks.get('items', []))
        return future_tasks

    def dumps_to_redis(self):
        d = {
            'state': self.state,
            'task': self.current_task_name,
            'calendar': self._calendar_id
        }
        redis_db.set(f'{self.user_id}_data', json.dumps(d))
