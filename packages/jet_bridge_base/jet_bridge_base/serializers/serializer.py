from collections import OrderedDict
from jet_bridge_base.fields.field import Field

try:
    from collections.abc import Mapping, Iterable
    from collections import OrderedDict
except ImportError:
    from collections import OrderedDict, Mapping, Iterable

import six

from jet_bridge_base.exceptions.validation_error import ValidationError
from jet_bridge_base.fields.field import Field, empty


class SerializerMetaclass(type):

    @classmethod
    def _get_declared_fields(cls, bases, attrs):
        # Start with base class fields (in reverse MRO), then update with local fields.
        all_fields = []

        # Process bases' declared fields before current class's.
        for base in reversed(bases):
            base_fields = getattr(base, '_declared_fields', None)
            if base_fields:
                # Only add fields not shadowed by local attrs
                for field_name, obj in base_fields.items():
                    if field_name not in attrs:
                        all_fields.append((field_name, obj))

        # Only pop later, after collecting names: minimize repeated lookups and repeated dict copying
        local_fields = []
        to_remove = []
        for field_name, obj in attrs.items():
            if isinstance(obj, Field):
                local_fields.append((field_name, obj))
                to_remove.append(field_name)

        # Remove after collection for lower mutation overhead
        for field_name in to_remove:
            attrs.pop(field_name)

        # Sort local fields by creation_counter
        if len(local_fields) > 1:
            # usually only a few fields, skip overhead for single
            local_fields.sort(key=lambda x: x[1].creation_counter)

        # Local fields should override base fields of the same name (unordered, so append local last)
        all_fields.extend(local_fields)

        # Use OrderedDict directly (much faster for bulk init)
        return OrderedDict(all_fields)

    def __new__(cls, name, bases, attrs):
        attrs['_declared_fields'] = cls._get_declared_fields(bases, attrs)
        return super(SerializerMetaclass, cls).__new__(cls, name, bases, attrs)


@six.add_metaclass(SerializerMetaclass)
class Serializer(Field):
    validated_data = None
    fields = []
    errors = None

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        self.data = kwargs.pop('data', None)
        self.meta = getattr(self, 'Meta', None)
        self.partial = kwargs.pop('partial', False)
        super(Serializer, self).__init__(*args, **kwargs)
        self.update_fields()

    def update_fields(self):
        self.fields = self.get_fields()

    def get_fields(self):
        result = []

        for field_name, field in self._declared_fields.items():
            field.field_name = field_name
            result.append(field)

        return result

    @property
    def readable_fields(self):
        if not self.fields or not isinstance(self.fields, Iterable):
            return []
        return list(filter(lambda x: not x.write_only, self.fields))

    @property
    def writable_fields(self):
        if not self.fields or not isinstance(self.fields, Iterable):
            return []
        return list(filter(lambda x: not x.read_only, self.fields))

    def run_validation(self, value):
        if value is empty:
            if self.required:
                # raise ValidationError('Field is required')
                self.error('required')

        value = self.to_internal_value(value)

        if self.many:
            try:
                value = list(map(lambda x: self.validate(x), value))
                assert value is not None, '.validate() should return the validated data'
            except ValidationError as e:
                raise e
        else:
            try:
                value = self.validate(value)
                assert value is not None, '.validate() should return the validated data'
            except ValidationError as e:
                raise e

        return value

    def is_valid(self, raise_exception=False):
        try:
            self.validated_data = self.run_validation(self.data)
            self.errors = None
        except ValidationError as e:
            self.validated_data = None
            self.errors = e.detail

        if self.errors and raise_exception:
            raise ValidationError(self.errors)

        return not bool(self.errors)

    def to_internal_value_item(self, value):
        result = OrderedDict()
        errors = OrderedDict()

        for field in self.writable_fields:
            field_value = field.get_value(value)

            if field_value is empty:
                if self.partial or not field.required:
                    continue

            validate_method = getattr(self, 'validate_' + field.field_name, None)

            try:
                validated_value = field.run_validation(field_value)
                if validate_method is not None:
                    validated_value = validate_method(validated_value)
                result[field.field_name] = validated_value
            except ValidationError as e:
                errors[field.field_name] = e

        if errors:
            raise ValidationError(errors)

        return result

    def to_representation_item(self, value):
        result = OrderedDict()

        for field in self.readable_fields:
            if isinstance(value, Mapping):
                field_value = value.get(field.field_name, empty)
            else:
                field_value = getattr(value, field.field_name, empty)

            if field_value is empty:
                if not field.required:
                    continue
                else:
                    field_value = None

            result[field.field_name] = field.to_representation(field_value)

        return result

    @property
    def representation_data(self):
        if self.instance is not None:
            return self.to_representation(self.instance)
        elif self.validated_data is not None:
            return self.to_representation(self.validated_data)

    def validate(self, attrs):
        return attrs

    def update(self, instance, validated_data):
        raise NotImplementedError('`update()` must be implemented.')

    def create(self, validated_data):
        raise NotImplementedError('`create()` must be implemented.')

    def save(self, **kwargs):
        if self.errors:
            raise AssertionError('You cannot call `.save()` on a serializer with invalid data.')

        validated_data = dict(
            list(self.validated_data.items()) +
            list(kwargs.items())
        )

        if self.instance is not None:
            self.instance = self.update(self.instance, validated_data)

            if self.instance is None:
                raise AssertionError('`update()` did not return an object instance.')

        else:
            self.instance = self.create(validated_data)

            if self.instance is None:
                raise AssertionError('`create()` did not return an object instance.')

        return self.instance
