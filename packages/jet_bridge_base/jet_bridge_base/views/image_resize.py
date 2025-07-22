import io
from six.moves import urllib
from PIL import Image

from jet_bridge_base.configuration import configuration
from jet_bridge_base.exceptions.not_found import NotFound
from jet_bridge_base.media_cache import cache
from jet_bridge_base.responses.redirect import RedirectResponse
from jet_bridge_base.views.base.api import APIView


class ImageResizeView(APIView):

    def create_thumbnail(self, file, thumbnail_path, max_width, max_height):
        img = Image.open(file)
        img.thumbnail((max_width, max_height), Image.LANCZOS)
        with io.BytesIO() as memory_file:
            img.save(memory_file, format=img.format, quality=85)
            memory_file.seek(0)
            configuration.media_save(thumbnail_path, memory_file.read())

    def get(self, request, *args, **kwargs):
        # TODO: Move to serializer
        # TODO: Add options dependant cache name

        path = request.get_argument('path')
        # Inline conversion to int just once
        max_width = int(request.get_argument('max_width', 320))
        max_height = int(request.get_argument('max_height', 240))
        # Faster external path check
        external_path = path[:8].lower() == 'https://' or path[:7].lower() == 'http://'
        
        try:
            if not cache.exists(path):
                if not external_path:
                    # Internal file path optimization
                    if not configuration.media_exists(path):
                        raise NotFound
                    file = configuration.media_open(path)
                else:
                    # Network I/O - cannot optimize much more unless using async
                    # Avoid unnecessary copying of file data
                    with urllib.request.urlopen(path) as fd:
                        data = fd.read()
                    file = io.BytesIO(data)

                # Only now build thumbnail path, as it's only ever needed here
                thumbnail_full_path = cache.full_path(path)
                # Avoid holding File I/Os or network open more than needed
                with file:
                    cache.clear_cache_if_needed()
                    self.create_thumbnail(file, thumbnail_full_path, max_width, max_height)
                    cache.add_file(path)

            return RedirectResponse(cache.url(path, request))
        except IOError as e:
            raise e
