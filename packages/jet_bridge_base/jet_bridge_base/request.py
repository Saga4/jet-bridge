import json
import os
import tempfile
import time
from json import JSONDecodeError

from jet_bridge_base.exceptions.request_error import RequestError
from jet_bridge_base.exceptions.validation_error import ValidationError
from jet_bridge_base.utils.conf import get_conf
from jet_bridge_base.utils.crypt import get_sha256_hash
from jet_bridge_base.utils.process import get_memory_usage
from six import string_types

from jet_bridge_base import settings
from jet_bridge_base.exceptions.missing_argument_error import MissingArgumentError

_ARG_DEFAULT = object()


class Request(object):

    session = None
    bridge_settings = None
    project = None
    environment = None
    resource_token = None
    sso_shared_data = None
    context = {}

    track_start_time = None
    track_start_memory_usage = None
    def __init__(
            self,
            method=None,
            protocol=None,
            host=None,
            path=None,
            path_kwargs=None,
            uri=None,
            query_arguments=None,
            headers=None,
            body=None,
            body_arguments=None,
            files=None,
            original_request=None,
            original_handler=None,
            action=None
    ):
        self.method = method
        self.protocol = protocol
        self.host = host
        self.path = path
        self.path_kwargs = path_kwargs
        self.uri = uri
        self.query_arguments = query_arguments if query_arguments is not None else {}
        self.headers = headers if headers is not None else {}
        self.body = body
        self.body_arguments = body_arguments if body_arguments is not None else {}
        self.files = files if files is not None else {}
        self.original_request = original_request
        self.original_handler = original_handler
        self.action = action

        content_type = self.headers.get('CONTENT_TYPE', '')

        # Faster JSON parsing path
        if content_type.startswith('application/json'):
            data = self.body
            if not isinstance(data, string_types):
                data = data.decode('utf-8', 'surrogatepass')
            try:
                self.data = json.loads(data) if data else {}
            except ValueError as e:
                raise RequestError(self, f'Incorrect JSON body: {e}')
        else:
            # Optimize: un-nest all inner functions and avoid extra list allocations
            results = {}
            for key, values in self.body_arguments.items():
                # Accept common cases: values is almost always a list, so avoid list(map(...))
                processed = []
                for value in values:
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except Exception:
                            pass
                    processed.append(value)
                if len(processed) > 1:
                    results[key] = processed
                elif len(processed) == 1:
                    results[key] = processed[0]
                else:
                    results[key] = None
            self.data = results

    def full_url(self):
        return self.protocol + "://" + self.host + self.uri

    def get_argument(self, name, default=_ARG_DEFAULT, strip=True):
        return self._get_argument(name, default, self.query_arguments, strip)

    def get_arguments(self, name, strip=False):
        return self._get_arguments(name, self.query_arguments, strip)

    def get_argument_safe(self, name, default=_ARG_DEFAULT):
        values = self.get_arguments(name)

        if len(values) == 0:
            value = default
        elif len(values) == 1:
            value = values[0]
        else:
            value = values

        return value

    def get_body_argument(self, name, default=_ARG_DEFAULT, strip=True):
        return self._get_argument(name, default, self.body_arguments, strip)

    def get_body_arguments(self, name, strip=True):
        return self._get_arguments(name, self.body_arguments, strip)

    def get_ip(self):
        return self.headers.get('X_REAL_IP')

    def get_stick_session(self):
        return self.headers.get('X_STICK_SESSION')

    def _get_argument(self, name, default, source, strip=True):
        args = self._get_arguments(name, source, strip=strip)
        if not args:
            if default is _ARG_DEFAULT:
                raise MissingArgumentError(name)
            return default
        return args[-1]

    def _get_arguments(self, name, source, strip=True):
        # Optimize: avoid attribute lookups in loop, use generator expression, avoid extra list() call
        values = source.get(name)
        if not values:
            return []
        if strip:
            return [v.decode('utf-8').strip() if isinstance(v, bytes) else v.strip() for v in values]
        else:
            return [v.decode('utf-8') if isinstance(v, bytes) else v for v in values]

    def get_bridge_settings(self):
        if self.bridge_settings:
            return self.bridge_settings

        bridge_settings_encoded = self.headers.get('X_BRIDGE_SETTINGS')

        if not bridge_settings_encoded:
            return

        from jet_bridge_base.utils.crypt import decrypt

        try:
            secret_key = settings.TOKEN.replace('-', '').lower()
            decrypted = decrypt(bridge_settings_encoded, secret_key)

            self.bridge_settings = {
                **json.loads(decrypted),
                'raw': bridge_settings_encoded
            }
        except Exception:
            return

        database_ssl_ca = self.bridge_settings.get('database_ssl_ca')
        database_ssl_cert = self.bridge_settings.get('database_ssl_cert')
        database_ssl_key = self.bridge_settings.get('database_ssl_key')

        temp_dir = os.path.join(tempfile.gettempdir(), 'ssl')

        try:
            os.makedirs(temp_dir)
        except OSError:
            pass

        if database_ssl_ca:
            self.bridge_settings['database_ssl_ca'] = self.save_file(temp_dir, '{}-ca.pem', database_ssl_ca)

        if database_ssl_cert:
            self.bridge_settings['database_ssl_cert'] = self.save_file(temp_dir, '{}-cert.pem', database_ssl_cert)

        if database_ssl_key:
            self.bridge_settings['database_ssl_key'] = self.save_file(temp_dir, '{}-key.pem', database_ssl_key)

        return self.bridge_settings

    def save_file(self, dir_path, name, content):
        file_hash = get_sha256_hash(content)
        file_path = os.path.join(dir_path, name.format(file_hash))

        with open(file_path, 'w') as f:
            f.write(content)

        return f.name

    def start_track(self):
        self.track_start_time = time.time()
        self.track_start_memory_usage = get_memory_usage()

    def get_track_time(self):
        if self.track_start_time is None:
            return
        return round(time.time() - self.track_start_time, 3)

    def get_track_memory_usage(self):
        if self.track_start_memory_usage is None:
            return
        return get_memory_usage() - self.track_start_memory_usage

    def apply_rls_if_enabled(self):
        conf = get_conf(self)

        if conf.get('rls_type') == 'supabase' and conf.get('rls_sso'):
            shared_data = (self.sso_shared_data or {}).get(conf['rls_sso'], {})
            user_id = shared_data.get('user_id')

            self.session.execute('SET ROLE authenticated')
            self.session.execute('SELECT set_config(\'request.jwt.claim.sub\', :uid, TRUE)', {'uid': user_id})
