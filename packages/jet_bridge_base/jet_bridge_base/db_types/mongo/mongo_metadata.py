from .mongo_table import MongoTable


class MongoMetadata(object):
    def __init__(self, tables=None, schema=None):
        # Use a generator expression for deserialization
        self.tables = [MongoTable.deserialize(x) for x in tables] if tables else []
        self.schema = schema

    def append_table(self, table):
        self.tables.append(table)

    @staticmethod
    def deserialize(obj):
        return MongoMetadata(**obj)

    def serialize(self):
        return {
            'tables': list(map(lambda x: x.serialize(), self.tables)),
            'schema': self.schema
        }
