from social_core.backends.utils import load_backends
from social_core.utils import get_strategy


STRATEGY_PATH = 'jet_bridge_base.external_auth.strategy.JetBridgeStrategy'
STORAGE_PATH = 'jet_bridge_base.external_auth.storage.JetBridgeStorage'


def load_strategy(request_handler, request, config):
    return get_strategy(STRATEGY_PATH, STORAGE_PATH, request_handler, request, config)


def load_backends_classes(backend_paths):
    # Assumes backend_paths is an ordered sequence matching the order of backends.values()
    backends = load_backends(backend_paths, force_load=True)
    return {path: backend for path, backend in zip(backend_paths, backends.values())}

