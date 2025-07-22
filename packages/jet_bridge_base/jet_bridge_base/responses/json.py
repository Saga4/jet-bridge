from __future__ import absolute_import

from jet_bridge_base import encoders
from jet_bridge_base.responses.base import Response


class JSONResponse(Response):
    encoder_class = encoders.JSONEncoder

    def __init__(self, *args, **kwargs):
        self.rendered_data = kwargs.pop('rendered_data', None)
        super(JSONResponse, self).__init__(*args, **kwargs)

    def default_headers(self):
        return {'Content-Type': 'application/json'}

    def render(self):
        rendered_data = self.rendered_data
        if rendered_data is not None:
            return rendered_data

        data = self.data
        if data is None:
            return

        encoder_class = self.encoder_class
        # Use encoder_class directly for much faster serialization
        encoded = encoder_class().encode(data)
        self.rendered_data = encoded
        return encoded
