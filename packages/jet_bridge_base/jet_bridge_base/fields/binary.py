from bson import ObjectId
import binascii

from jet_bridge_base.fields.field import Field


class BinaryField(Field):
    def to_internal_value_item(self, value):
        column = self.context.get('model_field')
        if column is not None \
                and hasattr(column, 'params') \
                and hasattr(column.params, 'get') \
                and column.params.get('type') == 'object_id':
            return ObjectId(value)
        else:
            return binascii.unhexlify(value)

    def to_representation_item(self, value):
        # Use the native .hex() method instead of binascii.hexlify().decode()
        if isinstance(value, bytes):
            return value.hex()
        elif isinstance(value, ObjectId):
            # ObjectId.binary is bytes as well
            return value.binary.hex()
