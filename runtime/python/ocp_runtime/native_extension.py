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
    parser.add_argument('--verification', action='store_true', help='Expose independent local job verification')
    parser.add_argument('--evidence', action='store_true', help='Expose preparation and checked explanation (requires --verification)')
    parser.add_argument('--checker-factory', help='Trusted installed checker MODULE:FACTORY, used only with --verification')
    parser.add_argument('--evidence-factory', help='Trusted installed evidence MODULE:FACTORY, used only with --evidence')
    args = parser.parse_args()
    if args.checker_factory and not args.verification:
        parser.error('--checker-factory requires --verification')
    if args.evidence and not args.verification:
        parser.error('--evidence requires --verification')
    if args.evidence_factory and not args.evidence:
        parser.error('--evidence-factory requires --evidence')
    registry = None
    if args.verification:
        from conformance.assessment import load_registry
        registry = load_registry(args.checker_factory)
    from .native_mcp import create_native_mcp
    with LocalAPI(load_extension(args.extension)) as local:
        clients = {name: local.client(name) for name in local.app.state.domain_ids}
        verifier = None
        if args.verification:
            from .native_verification import local_verifier
            verifier = local_verifier(local.app.state.native_store, registry=registry)
        evidence = None
        if args.evidence:
            from .native_evidence import EvidenceService
            from .native_evidence_registry import load_evidence_registry
            evidence = EvidenceService(clients, local.app.state.native_store, registry=registry,
                                       evidence_registry=load_evidence_registry(args.evidence_factory))
        create_native_mcp(clients, verifier=verifier, evidence=evidence).run(transport='stdio')


if __name__ == '__main__':
    # Keep Extension's identity in the importable module. Running this file as
    # __main__ otherwise creates a second dataclass and rejects valid factories.
    from .native_extension import main as installed_main
    installed_main()
