"""Strict CSV preparation for the existing spherical coordinates profile."""
import csv
from io import StringIO
import math
import re


def rows(text, columns):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 65536:
        raise ValueError('CSV_SIZE_LIMIT')
    try:
        reader = csv.DictReader(StringIO(text), strict=True)
        if reader.fieldnames != columns:
            raise ValueError('CSV_COLUMNS: ' + ','.join(columns))
        result = list(reader)
    except csv.Error:
        raise ValueError('CSV_MALFORMED') from None
    if not result or len(result) > 64:
        raise ValueError('CSV_ROW_LIMIT')
    for index, row in enumerate(result, 2):
        if set(row) != set(columns) or any(value is None or not value.strip() for value in row.values()):
            raise ValueError(f'CSV_MISSING_OR_EXTRA_FIELD: row {index}')
        if row['id'] != row['id'].strip():
            raise ValueError(f'CSV_ID_WHITESPACE: row {index}')
    if len({row['id'] for row in result}) != len(result):
        raise ValueError('CSV_DUPLICATE_ID')
    return result


def integer(value):
    if not re.fullmatch(r'0|[1-9][0-9]*', value):
        raise ValueError('CSV_INTEGER_KG_REQUIRED')
    return int(value)


def location(row):
    try:
        latitude, longitude = float(row['latitude']), float(row['longitude'])
    except ValueError:
        raise ValueError('CSV_COORDINATE_REQUIRED') from None
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('CSV_COORDINATE_RANGE')
    return {'latitude': latitude, 'longitude': longitude}


def coordinates_from_csv(depot, visits, vehicles, *, distance_model):
    """Units are in column names; distance assumptions require an explicit choice."""
    if distance_model != 'haversine':
        raise ValueError('UNSUPPORTED_DISTANCE_MODEL: provide a road matrix with routing.basic instead')
    origins = rows(depot, ['id', 'latitude', 'longitude'])
    if len(origins) != 1:
        raise ValueError('ONE_DEPOT_REQUIRED')
    data = {'depot': {'id': origins[0]['id'], 'location': location(origins[0])},
        'load_unit': 'kg',
        'distance': {'model': 'haversine', 'earth_radius_m': 6371000, 'rounding': 'ceil', 'unit': 'meter'},
        'visits': [{'id': row['id'], 'demand': integer(row['demand_kg']), 'location': location(row)}
                   for row in rows(visits, ['id', 'latitude', 'longitude', 'demand_kg'])],
        'vehicles': [{'id': row['id'], 'capacity': integer(row['capacity_kg'])}
                     for row in rows(vehicles, ['id', 'capacity_kg'])]}
    from ocp_routing.coordinates import check_input
    check_input(data)
    return data
