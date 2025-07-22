import re
import six

from jet_bridge_base.db_types import inspect_uniform
from jet_bridge_base.exceptions.validation_error import ValidationError


def serialize_validation_error(exc):
    def process(e, root=False):
        if isinstance(e.detail, dict):
            return dict(map(lambda x: (x[0], process(x[1])), e.detail.items()))
        elif isinstance(e.detail, list):
            return list(map(lambda x: process(x), e.detail))
        elif root:
            return {'non_field_errors': [e.detail]}
        else:
            return e.detail

    return process(exc, root=True)


def validation_error_from_database_error(e, model):
    orig = getattr(e, 'orig', None)
    if orig is not None:
        args = getattr(orig, 'args', None)
        if args:
            # Choose message depending on arg count
            try:
                if len(args) == 1:
                    message = args[0]
                elif len(args) == 2:
                    message = args[1]
                else:
                    message = args
            except (TypeError, IndexError):
                message = args

            message = str(message)  # always string in Py3+

            for regex, field_index, value_index in UNIQUE_ERR_REGEXES:
                m = regex.search(message)
                if m:
                    mapper = inspect_uniform(model)
                    columns = {col.key: col for col in mapper.columns}
                    column_name = m.group(field_index)
                    if column_name in columns:
                        return ValidationError({column_name: ValidationError('record with the same value already exists')})

            return ValidationError(message)
    return ValidationError('Query failed')

UNIQUE_ERR_REGEXES = [
    (re.compile(r'Key\s\((.+)\)=\((.+)\)\salready\sexists', re.IGNORECASE | re.MULTILINE), 1, 2),  # PostgreSQL
    (re.compile(r'Duplicate\sentry\s\'(.+)\'\sfor key\s\'(.+)\'', re.IGNORECASE | re.MULTILINE), 2, 1),  # MySQL
    (re.compile(r'UNIQUE\sconstraint\sfailed\:\s(.+)\.(.+)', re.IGNORECASE | re.MULTILINE), 2, None)  # SQLite
]
