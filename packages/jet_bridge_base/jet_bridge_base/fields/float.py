import six

from jet_bridge_base.fields.field import Field


class FloatField(Field):
    field_error_messages = {
        'invalid': 'not a valid float'
    }

    def to_internal_value_item(self, value):
        if value is None:
            return

        value_str = str(value).strip()
        value_lower = value_str.lower()

        if value_lower == 'true':
            return 1
        elif value_lower == 'false':
            return 0

        try:
            return float(value_str)
        except (ValueError, TypeError):
            self.error('invalid')

    def to_representation_item(self, value):
        if value is None:
            return
        return value
