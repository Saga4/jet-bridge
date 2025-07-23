import re
from sqlalchemy.exc import SQLAlchemyError

from .common import sql_get_session_engine


def fetch_postgresql_type_code_to_sql_type(session):
    from sqlalchemy.dialects.postgresql.base import ischema_names

    result = {}

    # Precompile regexes for better performance
    strip_array_re = re.compile(r"\[\]$")
    strip_parenthesis_re = re.compile(r"\(.*\)")

    try:
        types_cursor = session.execute('''
            SELECT 
                pg_catalog.format_type(oid, NULL) AS format_type,
                oid 
            FROM 
                pg_type
        ''')

        for pg_type in types_cursor:
            type_code = pg_type['oid']
            format_type = pg_type['format_type']

            # Fast-path: only regex if needed for array or parenthesis
            attype = format_type
            if '(' in attype:
                attype = strip_parenthesis_re.sub("", attype)
            is_array = attype.endswith("[]")
            if is_array:
                attype = strip_array_re.sub("", attype)

            if attype.startswith('interval'):
                attype = 'interval'

            sql_type = ischema_names.get(attype)
            if sql_type:
                result[type_code] = sql_type

        session.commit()
    except SQLAlchemyError:
        session.rollback()

    return result


def fetch_type_code_to_sql_type(session):
    if sql_get_session_engine(session) == 'postgresql':
        return fetch_postgresql_type_code_to_sql_type(session)
