from six.moves.urllib_parse import quote

from jet_bridge_base import settings
from jet_bridge_base.responses.base import Response
from jet_bridge_base.responses.redirect import RedirectResponse
from jet_bridge_base.status import HTTP_400_BAD_REQUEST
from jet_bridge_base.views.base.api import BaseAPIView


class RegisterView(BaseAPIView):

    def get(self, request, *args, **kwargs):
        project = settings.PROJECT
        if not project:
            return Response('Project name is not set', status=HTTP_400_BAD_REQUEST)

        token_setting = settings.TOKEN
        if not token_setting:
            return Response('Project token is not set', status=HTTP_400_BAD_REQUEST)

        token = request.get_argument('token', '')
        environment_type = settings.ENVIRONMENT_TYPE
        environment = settings.ENVIRONMENT
        web_base_url = settings.WEB_BASE_URL
        database_engine = settings.DATABASE_ENGINE

        request_full_url = request.full_url()

        # Only one if-statement, branch assignment
        if web_base_url.startswith('https') and not request_full_url.startswith('https'):
            web_base_url = 'http' + web_base_url[5:]

        # Assemble URL using f-strings for speed.
        if environment:
            url = f'{web_base_url}/builder/{project}/{environment}/resources/database/create/'
        else:
            url = f'{web_base_url}/builder/{project}/resources/database/create/'

        # Build parameters as tuples, one pass for conditional additions
        # Use list literal for initial entries, extend if conditionals needed.
        parameters = [
            ('engine', database_engine),
            ('referrer', request_full_url.encode('utf8')),
        ]
        if token:
            parameters.append(('token', token))
        if environment_type:
            parameters.append(('environment_type', environment_type))

        # Fast query string assembly with generator, f-string and quote
        query_string = '&'.join(
            f'{k}={quote(v)}' for k, v in parameters
        )

        # Return response
        return RedirectResponse(f'{url}#{query_string}')
