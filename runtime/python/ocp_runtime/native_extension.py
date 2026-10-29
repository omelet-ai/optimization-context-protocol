"""Opt-in installed domain registration; no automatic plugin discovery.

Factories are trusted executable host configuration, never supplied by an LLM,
request, catalog or schema URI. This API is additive; native wire v1 is unchanged.
"""
import argparse
from dataclasses import dataclass
from importlib import import_module
import re

from .native_server import LocalAPI, Registration

EXTENSION_API = '0.1.0'


@dataclass(frozen=True)
class Extension:
    api_version: str
    registrations: tuple


def load_extension(factory):
    if not isinstance(factory, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*', factory):
        raise ValueError('INVALID_EXTENSION_FACTORY')
    module, function = factory.split(':')
    try:
        extension = getattr(import_module(module), function)()
    except Exception as error:
        raise ValueError('INVALID_EXTENSION_FACTORY') from error
    if not isinstance(extension, Extension) or extension.api_version != EXTENSION_API:
        raise ValueError('EXTENSION_VERSION_MISMATCH')
    registrations = extension.registrations
    if not isinstance(registrations, tuple) or not registrations or any(not isinstance(r, Registration) or not callable(r.solve) for r in registrations):
        raise ValueError('INVALID_EXTENSION_REGISTRATION')
    ids = [r.domain.problem_type for r in registrations]
    if len(set(ids)) != len(ids):
        raise ValueError('DUPLICATE_DOMAIN')
    return registrations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extension', required=True)
    args = parser.parse_args()
    from .native_mcp import create_native_mcp
    with LocalAPI(load_extension(args.extension)) as local:
        create_native_mcp({name: local.client(name) for name in local.app.state.domain_ids}).run(transport='stdio')


if __name__ == '__main__':
    # Keep Extension's identity in the importable module. Running this file as
    # __main__ otherwise creates a second dataclass and rejects valid factories.
    from .native_extension import main as installed_main
    installed_main()
