"""Prepare an exact operation request; no dispatcher, execution port or journal."""
from copy import deepcopy
from jsonschema import Draft202012Validator

from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.operations import EXTENSION, operations, reference
from ocp_candidate.server_package import lint_package, validate_request, PackageError
from .prepare import _prepare_value, InputError, CONVERTER_VERSION


def prepare_operation(descriptor, operation_id, payload, *, expected, context=None,
                      configuration=None, format_id=None, format_version=None, converters=None):
    """Convert supplied bytes/direct JSON into a non-authorized, non-executed plan.

    Metadata may select only a local, registered pure converter. No file path,
    operation handler, trusted principal, database or remote endpoint is accepted.
    """
    lint_package(descriptor, supported_extensions=(EXTENSION,))
    operation = next((item for item in operations(descriptor) if item['id'] == operation_id), None)
    if operation is None:
        raise InputError('OPERATION_UNKNOWN')
    current = reference(descriptor, operation)
    if expected != current:
        raise InputError('OPERATION_REFERENCE_CHANGED')
    if (format_id is None) != (format_version is None):
        raise InputError('OPERATION_FORMAT_REFERENCE_INCOMPLETE')
    fingerprint(context)
    context_schema = operation.get('context_schema')
    if context_schema:
        if context is None or not Draft202012Validator(descriptor['schemas'][context_schema]).is_valid(context):
            raise InputError('OPERATION_CONTEXT_REQUIRED_OR_INVALID')
    elif context is not None:
        raise InputError('OPERATION_CONTEXT_UNSUPPORTED')
    if operation['kind'] != 'optimization' and configuration is not None:
        raise InputError('OPERATION_CONFIGURATION_UNSUPPORTED')
    parsed = _prepare_value(operation.get('input_formats', []), payload, format_id=format_id,
                            format_version=format_version, converters=converters)
    request = parsed.pop('value')
    schema = descriptor['schemas'][operation['request_schema']]
    invalid = next(Draft202012Validator(schema).iter_errors(request), None)
    if invalid is not None:
        raise InputError('OPERATION_REQUEST_INVALID', pointer='/' + '/'.join(map(str, invalid.absolute_path)))
    effective = None
    if operation['kind'] == 'optimization':
        try:
            effective = validate_request(descriptor, request, {} if configuration is None else configuration)
        except PackageError as error:
            raise InputError(error.code, pointer=error.path) from None
    result = {'kind': 'prepared_operation_request', 'status': 'prepared',
              'operation': current, 'operation_kind': operation['kind'],
              'request': request, 'request_fingerprint': fingerprint(request),
              'context': deepcopy(context), 'context_fingerprint': fingerprint(context),
              'configuration': effective, 'configuration_fingerprint': fingerprint(effective),
              **parsed, 'converter_version': CONVERTER_VERSION,
              'authorization': 'not_evaluated', 'execute_calls': 0, 'effects': 'none'}
    result['preparation_fingerprint'] = fingerprint(result)
    return result
