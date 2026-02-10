import importlib
import logging

logger = logging.getLogger(__name__)

def load(name):
    try:
        return importlib.import_module(f".{name}", package="saturn.providers")
    except ModuleNotFoundError:
        raise ValueError(
            f"Unknown beacon provider: '{name}'. "
            f"Create saturn/providers/{name}.py or check your [beacon] provider setting."
        )
