def get_table_name(metadata, table):
    schema = table.schema       # cache attribute lookup
    if schema and schema != metadata.schema:
        return f'{schema}.{table.name}'   # faster than .format()
    else:
        return str(table.name)
