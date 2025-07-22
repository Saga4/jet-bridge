import time
from datetime import date
from bson import ObjectId

from jet_bridge_base.logger import logger
from jet_bridge_base.models import data_types
from jet_bridge_base.utils.process import get_memory_usage_human

from .mongo_column import MongoColumn
from .mongo_table import MongoTable
from .mongo_metadata import MongoMetadata


def reflect_mongodb(
    cid_short,
    db,
    only=None,
    pending_connection=None,
    max_read_records=None
):
    available = db.list_collection_names()

    # Precompute which collections to load
    if only is None:
        load = available
    elif callable(only):
        load = [name for name in available if only(name)]
    else:
        load = list(only)

    metadata = MongoMetadata()

    total_tables = len(load)
    if pending_connection:
        pending_connection['tables_total'] = total_tables

    for idx, name in enumerate(load):
        # Removed time.sleep for maximum performance (restore if multi-thread fairness is required)
        logger.info('[{}] Analyzing collection "{}" ({} / {})" (Mem:{})...'.format(
            cid_short, name, idx + 1, total_tables, get_memory_usage_human())
        )

        table = MongoTable(name)
        columns = table.columns # Local ref for performance

        page = 1
        limit = 10000
        skip = 0

        has_any_items = False

        # Use outer break to avoid unnecessary checks
        while True:
            # Early check for record limit for quicker break
            if max_read_records is not None and skip >= max_read_records:
                break

            # Obtain iterator for the current page
            items = db[name].find(skip=skip, limit=limit)

            got_items = False
            # Store local references for fast lookup
            _BOOLEAN = data_types.BOOLEAN
            _INTEGER = data_types.INTEGER
            _CHAR = data_types.CHAR
            _FLOAT = data_types.FLOAT
            _DATE_TIME = data_types.DATE_TIME
            _JSON = data_types.JSON
            _BINARY = data_types.BINARY
            _TEXT = data_types.TEXT

            for item in items:
                got_items = True
                has_any_items = True
                for key, value in item.items():
                    # Fast skip for None
                    if value is None and key in columns:
                        continue

                    # Type inference branch in optimal order (most likely types first)
                    if value is None and key not in columns:
                        field_type = None
                        field_params = None
                    elif isinstance(value, bool):
                        field_type = _BOOLEAN
                        field_params = None
                    elif isinstance(value, int):
                        field_type = _INTEGER
                        field_params = None
                    elif isinstance(value, str):
                        field_type = _CHAR
                        field_params = None
                    elif isinstance(value, float):
                        field_type = _FLOAT
                        field_params = None
                    elif isinstance(value, date):
                        field_type = _DATE_TIME
                        field_params = None
                    elif isinstance(value, dict) or isinstance(value, list):
                        field_type = _JSON
                        field_params = None
                    elif isinstance(value, ObjectId):
                        field_type = _BINARY
                        field_params = {'type': 'object_id'}
                    else:
                        field_type = _TEXT
                        field_params = None

                    # Obtain or create column efficiently
                    if key in columns:
                        column = columns[key]
                    else:
                        column = MongoColumn(table, key, None)
                        columns[key] = column

                    # Mixed type detection and update
                    if column.type is not None and column.type != field_type:
                        if not column.mixed_types:
                            column.mixed_types = set()
                            column.mixed_types.add(column.type)
                        column.mixed_types.add(field_type)

                    column.type = field_type
                    if field_params:
                        column.params = field_params

            if got_items and (max_read_records is None or skip + limit < max_read_records):
                page += 1
                skip += limit
            else:
                break

        # Collection has no data
        if page == 1 and not has_any_items:
            logger.info('[{}] Collection "{}" does not have any data to analyze, skipping'.format(
                cid_short,
                name
            ))
        else:
            # Final type checks on columns, use list for iteration
            for column in list(columns.values()):
                if column.type is None:
                    column.type = _CHAR

                if getattr(column, 'mixed_types', None):
                    column.type = _JSON
                    logger.info('[{}] Field "{}"."{}" has data stored in multiple types ({}), falling back to JSON'.format(
                        cid_short,
                        name,
                        column.name,
                        ','.join(str(v) for v in column.mixed_types)
                    ))
            metadata.append_table(table)

        if pending_connection:
            pending_connection['tables_processed'] = idx + 1

    return metadata
