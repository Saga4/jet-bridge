from bson import ObjectId
import binascii

from jet_bridge_base.fields.field import Field


class BinaryField(Field):
    def to_internal_value_item(self, value):
        column = self.context.get('model_field')
        # Fastest path: only try to access .params and .get if column is not None
        if column is not None:
            try:
                # Check if the type is 'object_id'
                if column.params.get('type', None) == 'object_id':
                    return ObjectId(value)
            except AttributeError:
                pass
        return binascii.unhexlify(value)

    def to_representation_item(self, value):
        if isinstance(value, bytes):
            return binascii.hexlify(value).decode('ascii')
        elif isinstance(value, ObjectId):
            return binascii.hexlify(value.binary).decode('ascii')
