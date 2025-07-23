from __future__ import absolute_import
import json

from six import string_types

from jet_bridge_base.fields.field import Field


class JSONField(Field):
    field_error_messages = {
        'invalid': 'not a valid JSON'
    }

    def __init__(self, *args, **kwargs):
        if 'allow_many' not in kwargs:
            kwargs['allow_many'] = True
        super(JSONField, self).__init__(*args, **kwargs)

    def to_internal_value_item(self, value):
        # Micro-opt: Avoid json.loads call for clearly not-JSON strings (non-brace/quote numbers/words)
        if isinstance(value, string_types):
            s = value.lstrip()
            # Only try to parse if likely JSON (starts with {, [, ", -, digit, t,f,n for true/false/null)
            if s and (s[0] in '{["-0123456789tfn'):
                try:
                    return json.loads(value)
                except ValueError:
                    return value
            return value
        return value

    def to_representation_item(self, value):
        return value
