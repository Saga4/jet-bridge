import datetime
import dateparser
import six

from jet_bridge_base.db import get_default_timezone
from jet_bridge_base.fields.field import Field
from functools import lru_cache


def get_timezone_from_str(value):
    if not value:
        return

    return datetime.datetime.strptime(value.replace(':', ''), '%z').tzinfo


def datetime_apply_default_timezone(value, request):
    # Fast exit if already aware
    if value.tzinfo is not None:
        return value

    # Only look up timezone if request is not None
    if request:
        default_timezone = _get_cached_default_timezone(request)
        if default_timezone:
            return value.replace(tzinfo=default_timezone)

    return value


# New helper: Cache timezone lookups to speed up repeated calls.
@lru_cache(maxsize=64)
def _get_cached_default_timezone(request):
    return get_default_timezone(request)


class DateTimeField(Field):
    field_error_messages = {
        'invalid': 'date has wrong format'
    }

    def to_internal_value_item(self, value):
        if value is None:
            return
        value = six.text_type(value).strip()

        try:
            result = dateparser.parse(value)
        except ValueError:
            result = None

        if result is None:
            self.error('invalid')

        return result

    def to_representation_item(self, value):
        if value is None:
            return

        request = self.context.get('request')
        value = datetime_apply_default_timezone(value, request)

        return value.isoformat()
