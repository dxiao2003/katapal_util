from __future__ import unicode_literals

import logging
from datetime import datetime, timedelta
from functools import wraps

import pytz
from django.utils import timezone
from phonenumber_field.phonenumber import PhoneNumber
from rest_framework.exceptions import ValidationError


from json import JSONEncoder
from uuid import UUID

from rest_framework.filters import SearchFilter

logger = logging.getLogger(__name__)

JSONEncoder_olddefault = JSONEncoder.default

def JSONEncoder_newdefault(self, o):
    if isinstance(o, UUID):
        return str(o)
    elif isinstance(o, datetime):
        return o.isoformat()
    else:
        return JSONEncoder_olddefault(self, o)

JSONEncoder.default = JSONEncoder_newdefault


class ShortCircuit(Exception):
    """
    To stop processing immediately and return a response, raise this and
    pass it the respone to be returned.
    """

    def __init__(self, response, *args, **kwargs):
        self.response = response
        super(ShortCircuit, self).__init__(*args, **kwargs)


def object_validator(clazz):
    def decorator(func):
        @wraps(func)
        def f(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except clazz.DoesNotExist:
                raise ValidationError("Invalid " + clazz.__name__)
        return f
    return decorator


class ObjectBuilder(object):

    def _set_property(self, property_name, value, force):
        if not hasattr(self, property_name) or force == True:
            setattr(self, property_name, value)

    def _add_elem(self, property_name, value, duplicate=False):
        list = getattr(self, property_name, [])
        if value not in list or duplicate:
            list.append(value)
        setattr(self, property_name, list)

    def _extend_elems(self, property_name, values, duplicate=False):
        for v in values:
            self._add_elem(property_name, v, duplicate)


def get_week_start(dt, tzname=None):
    """
    Computes the start of the week in the time zone specified in setting, or
    UTC by default.

    :param dt: The datetime
    :param setting: the autoreply setting
    :return: The start of the week of dt, relative to UTC
    """
    if tzname:
        tz = pytz.timezone(tzname)
    else:
        tz = pytz.utc

    if dt.tzinfo:
        dt = dt.astimezone(tz)
    else:
        dt = tz.localize(dt)

    start_day = dt - timedelta(days=dt.weekday())
    start_of_week = start_day.replace(hour=0, minute=0, second=0, microsecond=0)

    return start_of_week.astimezone(pytz.utc)


def start_end_from_interval(week_start, interval):

    start_time = week_start + timedelta(milliseconds=int(interval["start"]))
    end_time = start_time + timedelta(milliseconds=int(interval["duration"]))

    return start_time, end_time


def interval_from_start_end(week_start, start_time, end_time):
    duration = end_time - start_time
    start = start_time - week_start
    return {"start": int(start.total_seconds() * 1000),
            "duration": int(duration.total_seconds() * 1000)}


def find_next_valid_time(current_week_start, weekly_schedule, now=None,
                         validity_start_time=None):
    now = now or timezone.now()
    # get start/end times for all intervals in last, current and next week
    # in order to handle candidate times right on the edge between weeks
    all_start_end_times = [
        start_end_from_interval(week_start, i)
        for i in weekly_schedule
        for week_start in [current_week_start,
                           current_week_start - timedelta(days=7),
                           current_week_start + timedelta(days=7)]
        ]

    next_valid_time = datetime.max.replace(tzinfo=pytz.UTC)

    for start_time, end_time in all_start_end_times:
        if start_time <= now <= end_time:
            return now
        elif start_time >= now and next_valid_time >= start_time and \
                (not validity_start_time or start_time >= validity_start_time):
            next_valid_time = start_time

    return next_valid_time


def format_phonenumber(potential_number):
    try:
        number = PhoneNumber.from_string(potential_number)
        logger.debug("Got number in search for %s" % number)
        return str(number)
    except Exception as e:
        return potential_number


class RichSearchFilter(SearchFilter):
    def get_search_terms(self, request):
        params = request.query_params.get(self.search_param, '')
        return map(format_phonenumber, params.replace(',', ' ').split())


def split_into_words_by_char_count(s, chunk_size, max_from_end=None):
    """
    Split a string into an array of strings each of length at most chunk_size.
    Try to split on whitespace if possible (possibly resulting in chunks of size
    less than chunk_size), except if it would make the last word longer
    than max_from_end in which case just split it when we exceed the chunk size.

    :param s:
    :param chunk_size:
    :param max_from_end:
    :return:
    """
    if max_from_end is None:
        max_from_end = chunk_size / 10

    chunk_start = 0

    if len(s) == 0:
        return [""]

    chunks = []

    while chunk_start < len(s):
        chunk = s[chunk_start:chunk_start+chunk_size]
        if len(chunk) < chunk_size or \
                (chunk[-1].isspace() or s[chunk_start+chunk_size].isspace()):
            chunks.append(chunk)
            chunk_start += len(chunk)
        else:
            subchunks = chunk.rsplit(None, 1)
            if len(subchunks) == 1 or len(subchunks[1]) > max_from_end:
                chunks.append(chunk)
                chunk_start += len(chunk)
            else:
                chunks.append(subchunks[0])
                chunk_start += len(subchunks[0])

    return chunks