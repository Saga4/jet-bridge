import re
from sqlalchemy.exc import SQLAlchemyError

from .common import sql_get_session_engine


def fetch_postgresql_type_code_to_sql_type(session):
    from sqlalchemy.dialects.postgresql.base import ischema_names

    result = {}

    try:
        types_cursor = session.execute('''
            SELECT 
                pg_catalog.format_type(oid, NULL) AS format_type,
                oid 
            FROM 
                pg_type
        ''')

        ischema_lookup = ischema_names  # Local variable for faster access
        paren_re = _paren_re
        array_re = _array_re

        # Inline the hot functions for speed
        for pg_type in types_cursor:
            # Copied from:
            # def _get_column_info
            # site-packages/sqlalchemy/dialects/postgresql/base.py:3716

            type_code = pg_type['oid']
            format_type = pg_type['format_type']

            attype = format_type

            # Fast check if '(', avoid regex unless needed
            if '(' in attype:
                # strip (*) from character varying(5), timestamp(5)... etc.
                attype = paren_re.sub("", attype)

            # Fast check for arrays
            if attype.endswith('[]'):
                # strip '[]' from integer[], etc.
                attype = array_re.sub("", attype)
                # (We don't use is_array further, so not storing)

            if attype.startswith('interval'):
                attype = 'interval'

            sql_type = ischema_lookup.get(attype)
            if sql_type:
                result[type_code] = sql_type

        # session.commit() not required after only SELECTs, but kept per original intent
        session.commit()
    except SQLAlchemyError:
        session.rollback()

    return result


def fetch_type_code_to_sql_type(session):
    if sql_get_session_engine(session) == 'postgresql':
        return fetch_postgresql_type_code_to_sql_type(session)

_paren_re = re.compile(r"\(.*\)")

_array_re = re.compile(r"\[\]$")
