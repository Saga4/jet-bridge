from jet_bridge_base.utils.common import CollectionDict

from .mongo_column import MongoColumn


class MongoTable(object):
    def __init__(self, name, columns=None, comment=None, schema=None):
        self.name = name
        # Use a generator expression for improved performance and memory usage
        if columns:
            self.columns = CollectionDict(
                (x['name'], MongoColumn.deserialize(self, x)) for x in columns
            )
        else:
            self.columns = CollectionDict()
        self.comment = comment
        self.schema = schema

    def append_column(self, column):
        self.columns[column.name] = column

    @staticmethod
    def deserialize(obj):
        name = obj.pop('name')
        return MongoTable(name, **obj)

    def serialize(self):
        # Use a list comprehension for serialization instead of map+lambda
        return {
            'name': self.name,
            'columns': [x.serialize() for x in self.columns.values()],
            'comment': self.comment,
            'schema': self.schema
        }

    def __repr__(self):
        return self.name
