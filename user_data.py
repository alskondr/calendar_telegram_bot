import datetime
from dateutil.tz import gettz
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
        redis_data = redis_db.get(f'{user_id}_data')
        redis_dict = {}
        if redis_data is not None:
            redis_dict = json.loads(redis_data)
        
        self.user_id = user_id
        self._state = redis_dict.get('state', states.MAIN_STATE)
        self.service = None
        self._lock = Lock()
        self._current_task_name = redis_dict.get('task', '')
        self._calendar_id = redis_dict.get('calendar', '')
        self._tz_name = redis_dict.get('tz_name', 'UTC')

        redis_token = redis_db.get(f'{user_id}_token')
        if redis_token:
            credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(json.loads(redis_token))
            credentials.refresh(Request())
            if credentials.valid:
                self.service = build('calendar', 'v3', credentials=credentials)
                self.tz_name = self._get_primary_calendar_tz_name()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self.dumps_to_redis()

    @property
    def current_task_name(self):
        return self._current_task_name

    @current_task_name.setter
    def current_task_name(self, value):
        self._current_task_name = value
        self.dumps_to_redis()

    @property
    def tz_name(self):
        return self._tz_name

    @tz_name.setter
    def tz_name(self, value):
        self._tz_name = value
        self.dumps_to_redis()

    def init_service(self, authorization_code):
        try:
            flow.fetch_token(code=authorization_code)
        except InvalidGrantError:
            return False

        credentials = flow.credentials
        self.service = build('calendar', 'v3', credentials=credentials)
        redis_db.set(f'{self.user_id}_token', credentials.to_json())
        self.tz_name = self._get_primary_calendar_tz_name()
        return True

    def _get_primary_calendar_tz_name(self):
        calendar = self.service.calendars().get(calendarId='primary').execute()
        return calendar.get('timeZone', 'UTC')

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
                    'timeZone': self.tz_name
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
                'dateTime': dt.replace(tzinfo=gettz(self.tz_name)).isoformat()
            },
            'end': {
                'dateTime': (dt.replace(tzinfo=gettz(self.tz_name)) + datetime.timedelta(hours=1)).isoformat()
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
            self._lock.acquire()
            tasks = self.service.events().list(calendarId=calendar['id'],
                                               timeMin=min_date_time.isoformat(),
                                               timeMax=max_date_time.isoformat(),
                                               singleEvents=True,
                                               orderBy='startTime').execute()
            self._lock.release()
            day_tasks.extend(tasks.get('items', []))
        day_tasks.sort(key=lambda task: taskutils.get_task_start_time_utc(task))
        return day_tasks

    def get_day_tasks(self, date):
        dt_min = datetime.datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=gettz(self.tz_name))
        dt_max = datetime.datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=gettz(self.tz_name))
        return self.get_tasks(dt_min, dt_max)

    def get_future_tasks(self):
        future_tasks = []
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        for calendar in self.get_calendars():
            now_str = now.isoformat()
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
            'calendar': self._calendar_id,
            'tz_name': self.tz_name
        }
        redis_db.set(f'{self.user_id}_data', json.dumps(d))
