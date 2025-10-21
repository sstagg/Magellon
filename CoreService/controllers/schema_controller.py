"""
Schema Controller

Provides database schema metadata API endpoints for frontend.
Used by permission criteria builder to get entity and field information.
"""
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_role
from services.schema_introspection_service import SchemaIntrospectionService

import logging

logger = logging.getLogger(__name__)

schema_router = APIRouter(prefix="/db/schema", tags=["Schema"])

# Schema cache with TTL (Time-To-Live)
# Cache format: {cache_key: {'data': response, 'expires_at': datetime}}
_schema_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl_minutes = 60  # Cache for 1 hour


def _get_cached_schema(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Get cached schema if it exists and hasn't expired.

    Args:
        cache_key: Unique cache key

    Returns:
        Cached data or None if expired/not found
    """
    if cache_key not in _schema_cache:
        return None

    cache_entry = _schema_cache[cache_key]

    # Check if cache has expired
    if datetime.now() > cache_entry['expires_at']:
        logger.debug(f"Cache expired for key: {cache_key}")
        del _schema_cache[cache_key]
        return None

    logger.debug(f"Cache hit for key: {cache_key}")
    return cache_entry['data']


def _set_cached_schema(cache_key: str, data: Dict[str, Any]) -> None:
    """
    Store schema in cache with TTL.

    Args:
        cache_key: Unique cache key
        data: Schema data to cache
    """
    expires_at = datetime.now() + timedelta(minutes=_cache_ttl_minutes)
    _schema_cache[cache_key] = {
        'data': data,
        'expires_at': expires_at
    }
    logger.info(f"Cached schema with key: {cache_key}, expires at: {expires_at}")


def _invalidate_schema_cache() -> None:
    """Clear all schema cache entries."""
    global _schema_cache
    _schema_cache = {}
    logger.info("Schema cache invalidated")


@schema_router.get('/entities')
async def get_entities(
    include_system: bool = Query(False, description="Include system tables"),
    category: Optional[str] = Query(None, description="Filter by category (core/equipment/security/all)"),
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Get list of all available entities in the system.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Query Parameters:**
    - include_system: Include system/security tables (default: false)
    - category: Filter by category (core/equipment/security/all)

    **Returns:**
    ```json
    {
      "entities": [
        {
          "name": "msession",
          "table_name": "msession",
          "caption": "Microscopy Session",
          "description": "Imaging session grouping images",
          "category": "core",
          "icon": "microscope",
          "permissions_enabled": true
        }
      ],
      "total_count": 15
    }
    ```
    """
    try:
        entities = SchemaIntrospectionService.get_all_entities(
            include_system=include_system,
            category=category
        )

        return {
            "entities": entities,
            "total_count": len(entities)
        }

    except Exception as e:
        logger.exception('Error getting entities')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error getting entities: {str(e)}'
        )


@schema_router.get('/entity/{entity_name}')
async def get_entity_schema(
    entity_name: str,
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Get detailed schema for a specific entity.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Path Parameters:**
    - entity_name: Name of the entity (e.g., "msession", "image")

    **Returns:**
    ```json
    {
      "entity": {
        "name": "msession",
        "table_name": "msession",
        "caption": "Microscopy Session",
        "description": "Imaging session grouping images",
        "category": "core",
        "permissions_enabled": true,
        "fields": [
          {
            "name": "oid",
            "caption": "ID",
            "type": "uuid",
            "nullable": false,
            "primary_key": true,
            "searchable": true,
            "filterable": true
          },
          {
            "name": "name",
            "caption": "Session Name",
            "type": "string",
            "nullable": false,
            "max_length": 50,
            "searchable": true,
            "filterable": true
          }
        ],
        "relationships": []
      }
    }
    ```
    """
    try:
        schema = SchemaIntrospectionService.get_entity_schema(entity_name)
        return schema

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f'Error getting schema for entity: {entity_name}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error getting entity schema: {str(e)}'
        )


@schema_router.get('/entity/{entity_name}/field/{field_name}/options')
async def get_field_options(
    entity_name: str,
    field_name: str,
    search: Optional[str] = Query(None, description="Search term for filtering options"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of options"),
    db: Session = Depends(get_db),
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Get possible values for a field (for dropdowns, autocomplete).

    Used when building criteria expressions to provide autocomplete for foreign key fields.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Path Parameters:**
    - entity_name: Name of the entity
    - field_name: Name of the field

    **Query Parameters:**
    - search: Optional search term for filtering
    - limit: Maximum number of options (default: 100, max: 1000)

    **Returns:**
    ```json
    {
      "field": "user_id",
      "entity": "msession",
      "options": [
        {
          "value": "60492044-efbf-bdef-bfbd-544fefbfbdef",
          "label": "super",
          "description": "Super Administrator"
        }
      ],
      "total_count": 45,
      "has_more": true
    }
    ```
    """
    try:
        options = SchemaIntrospectionService.get_field_value_options(
            db=db,
            entity_name=entity_name,
            field_name=field_name,
            search=search,
            limit=limit
        )

        return options

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f'Error getting field options: {entity_name}.{field_name}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error getting field options: {str(e)}'
        )


@schema_router.get('/operators')
async def get_operators(
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Get list of supported operators for criteria building.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Returns:**
    List of operators with their applicable types and examples.
    """
    operators = [
        {
            'id': 'eq',
            'symbol': '=',
            'label': 'Equals',
            'applies_to': ['uuid', 'string', 'integer', 'decimal', 'boolean', 'datetime', 'date'],
            'example': '[user_id] = CurrentUserId()'
        },
        {
            'id': 'neq',
            'symbol': '!=',
            'label': 'Not Equals',
            'applies_to': ['uuid', 'string', 'integer', 'decimal', 'datetime', 'date'],
            'example': '[status] != \'archived\''
        },
        {
            'id': 'gt',
            'symbol': '>',
            'label': 'Greater Than',
            'applies_to': ['integer', 'decimal', 'datetime', 'date'],
            'example': '[priority] > 5'
        },
        {
            'id': 'gte',
            'symbol': '>=',
            'label': 'Greater Than or Equal',
            'applies_to': ['integer', 'decimal', 'datetime', 'date'],
            'example': '[created_date] >= \'2025-01-01\''
        },
        {
            'id': 'lt',
            'symbol': '<',
            'label': 'Less Than',
            'applies_to': ['integer', 'decimal', 'datetime', 'date'],
            'example': '[priority] < 10'
        },
        {
            'id': 'lte',
            'symbol': '<=',
            'label': 'Less Than or Equal',
            'applies_to': ['integer', 'decimal', 'datetime', 'date'],
            'example': '[end_date] <= \'2025-12-31\''
        },
        {
            'id': 'in',
            'symbol': 'IN',
            'label': 'In List',
            'applies_to': ['uuid', 'string', 'integer'],
            'example': '[status] IN (\'draft\', \'pending\', \'active\')'
        },
        {
            'id': 'not_in',
            'symbol': 'NOT IN',
            'label': 'Not In List',
            'applies_to': ['uuid', 'string', 'integer'],
            'example': '[status] NOT IN (\'archived\', \'deleted\')'
        },
        {
            'id': 'like',
            'symbol': 'LIKE',
            'label': 'Contains',
            'applies_to': ['string', 'text'],
            'example': '[name] LIKE \'%test%\''
        },
        {
            'id': 'is_null',
            'symbol': 'IS NULL',
            'label': 'Is Empty',
            'applies_to': ['all'],
            'example': '[deleted_date] IS NULL'
        },
        {
            'id': 'is_not_null',
            'symbol': 'IS NOT NULL',
            'label': 'Is Not Empty',
            'applies_to': ['all'],
            'example': '[user_id] IS NOT NULL'
        }
    ]

    return {'operators': operators}


@schema_router.get('/functions')
async def get_functions(
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Get list of supported functions for criteria expressions.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Returns:**
    List of built-in functions that can be used in criteria expressions.
    """
    functions = [
        {
            'name': 'CurrentUserId',
            'syntax': 'CurrentUserId()',
            'returns': 'uuid',
            'description': 'Returns the current authenticated user\'s ID',
            'example': '[user_id] = CurrentUserId()'
        },
        {
            'name': 'CurrentUser',
            'syntax': 'CurrentUser()',
            'returns': 'object',
            'description': 'Returns the current user object (use with property access)',
            'properties': [
                {'name': 'Oid', 'type': 'uuid'},
                {'name': 'USERNAME', 'type': 'string'},
            ],
            'example': '[owner_id] = CurrentUser().Oid'
        }
    ]

    return {'functions': functions}


@schema_router.get('/full')
async def get_full_schema(
    include_system: bool = Query(False, description="Include system tables"),
    force_refresh: bool = Query(False, description="Force cache refresh"),
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Get complete database schema with all entities, fields, operators, and functions.

    This endpoint returns EVERYTHING the frontend needs in a single JSON response:
    - All entities with their complete schemas
    - All supported operators
    - All supported functions
    - Metadata for building criteria expressions

    **Caching:**
    - Response is cached for 1 hour
    - Use `force_refresh=true` to bypass cache
    - Cache key includes `include_system` parameter

    **Recommended Usage:**
    - Frontend should call this once on app load
    - Cache the response in localStorage/memory
    - Use cached schema for criteria builder UI

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Response Size:** ~50-200KB (cacheable)

    **Returns:**
    ```json
    {
      "entities": {
        "msession": {
          "name": "msession",
          "caption": "Microscopy Session",
          "fields": [...],
          "relationships": [...]
        },
        "image": {...}
      },
      "operators": [...],
      "functions": [...],
      "metadata": {
        "generated_at": "2025-10-21T12:00:00Z",
        "version": "1.0",
        "total_entities": 9,
        "cached": false
      }
    }
    ```
    """
    try:
        # Generate cache key
        cache_key = f"full_schema_sys_{include_system}"

        # Check cache unless force refresh requested
        if not force_refresh:
            cached_data = _get_cached_schema(cache_key)
            if cached_data is not None:
                # Add cache hit indicator
                cached_data['metadata']['cached'] = True
                return cached_data

        logger.info(f"Generating full schema (include_system={include_system})")

        # Get all entities
        entities_list = SchemaIntrospectionService.get_all_entities(
            include_system=include_system
        )

        # Build complete schema for each entity
        entities_dict = {}
        for entity_info in entities_list:
            entity_name = entity_info['name']
            try:
                schema = SchemaIntrospectionService.get_entity_schema(entity_name)
                entities_dict[entity_name] = schema['entity']
            except Exception as e:
                logger.warning(f"Failed to get schema for {entity_name}: {e}")
                continue

        # Get operators
        operators = [
            {
                'id': 'eq',
                'symbol': '=',
                'label': 'Equals',
                'applies_to': ['uuid', 'string', 'integer', 'decimal', 'boolean', 'datetime', 'date'],
                'example': '[user_id] = CurrentUserId()',
                'requires_value': True
            },
            {
                'id': 'neq',
                'symbol': '!=',
                'label': 'Not Equals',
                'applies_to': ['uuid', 'string', 'integer', 'decimal', 'datetime', 'date'],
                'example': '[status] != \'archived\'',
                'requires_value': True
            },
            {
                'id': 'gt',
                'symbol': '>',
                'label': 'Greater Than',
                'applies_to': ['integer', 'decimal', 'datetime', 'date'],
                'example': '[priority] > 5',
                'requires_value': True
            },
            {
                'id': 'gte',
                'symbol': '>=',
                'label': 'Greater Than or Equal',
                'applies_to': ['integer', 'decimal', 'datetime', 'date'],
                'example': '[created_date] >= \'2025-01-01\'',
                'requires_value': True
            },
            {
                'id': 'lt',
                'symbol': '<',
                'label': 'Less Than',
                'applies_to': ['integer', 'decimal', 'datetime', 'date'],
                'example': '[priority] < 10',
                'requires_value': True
            },
            {
                'id': 'lte',
                'symbol': '<=',
                'label': 'Less Than or Equal',
                'applies_to': ['integer', 'decimal', 'datetime', 'date'],
                'example': '[end_date] <= \'2025-12-31\'',
                'requires_value': True
            },
            {
                'id': 'in',
                'symbol': 'IN',
                'label': 'In List',
                'applies_to': ['uuid', 'string', 'integer'],
                'example': '[status] IN (\'draft\', \'pending\', \'active\')',
                'requires_value': True,
                'value_type': 'list'
            },
            {
                'id': 'not_in',
                'symbol': 'NOT IN',
                'label': 'Not In List',
                'applies_to': ['uuid', 'string', 'integer'],
                'example': '[status] NOT IN (\'archived\', \'deleted\')',
                'requires_value': True,
                'value_type': 'list'
            },
            {
                'id': 'like',
                'symbol': 'LIKE',
                'label': 'Contains',
                'applies_to': ['string', 'text'],
                'example': '[name] LIKE \'%test%\'',
                'requires_value': True
            },
            {
                'id': 'is_null',
                'symbol': 'IS NULL',
                'label': 'Is Empty',
                'applies_to': ['all'],
                'example': '[deleted_date] IS NULL',
                'requires_value': False
            },
            {
                'id': 'is_not_null',
                'symbol': 'IS NOT NULL',
                'label': 'Is Not Empty',
                'applies_to': ['all'],
                'example': '[user_id] IS NOT NULL',
                'requires_value': False
            }
        ]

        # Get functions
        functions = [
            {
                'name': 'CurrentUserId',
                'syntax': 'CurrentUserId()',
                'returns': 'uuid',
                'description': 'Returns the current authenticated user\'s ID',
                'example': '[user_id] = CurrentUserId()',
                'category': 'user'
            },
            {
                'name': 'CurrentUser',
                'syntax': 'CurrentUser()',
                'returns': 'object',
                'description': 'Returns the current user object (access properties with dot notation)',
                'properties': [
                    {'name': 'Oid', 'type': 'uuid', 'description': 'User ID'},
                    {'name': 'USERNAME', 'type': 'string', 'description': 'Username'},
                ],
                'example': '[owner_id] = CurrentUser().Oid',
                'category': 'user'
            }
        ]

        # Get logical operators
        logical_operators = [
            {
                'id': 'and',
                'symbol': 'AND',
                'label': 'And',
                'example': '[owner_id] = CurrentUserId() AND [status] = \'active\''
            },
            {
                'id': 'or',
                'symbol': 'OR',
                'label': 'Or',
                'example': '[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()'
            }
        ]

        # Get example criteria
        examples = [
            {
                'use_case': 'Users can only see their own records',
                'entity': 'msession',
                'criteria': '[user_id] = CurrentUserId()',
                'description': 'Filter where user_id equals the current user ID',
                'complexity': 'simple'
            },
            {
                'use_case': 'Users can see records they own OR are assigned to',
                'entity': 'project',
                'criteria': '[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()',
                'description': 'Filter where owner or assigned user is current user',
                'complexity': 'medium'
            },
            {
                'use_case': 'Users can only see active records they own',
                'entity': 'msession',
                'criteria': '[user_id] = CurrentUserId() AND [status] = \'active\'',
                'description': 'Filter where owner is current user and status is active',
                'complexity': 'medium'
            },
            {
                'use_case': 'Users can see non-archived records',
                'entity': 'project',
                'criteria': '[status] != \'archived\'',
                'description': 'Filter where status is not archived',
                'complexity': 'simple'
            },
            {
                'use_case': 'Users can see records in specific statuses',
                'entity': 'project',
                'criteria': '[status] IN (\'draft\', \'pending\', \'active\')',
                'description': 'Filter where status is in the specified list',
                'complexity': 'simple'
            }
        ]

        # Build metadata
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'version': '1.0',
            'total_entities': len(entities_dict),
            'include_system': include_system,
            'cache_key': cache_key,
            'cached': False
        }

        response = {
            'entities': entities_dict,
            'operators': operators,
            'logical_operators': logical_operators,
            'functions': functions,
            'examples': examples,
            'metadata': metadata
        }

        # Cache the response
        _set_cached_schema(cache_key, response)

        return response

    except Exception as e:
        logger.exception('Error generating full schema')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error generating full schema: {str(e)}'
        )


@schema_router.delete('/cache')
async def invalidate_schema_cache(
    _: UUID = Depends(get_current_user_id),
    __: None = Depends(require_role('Administrator'))
):
    """
    Invalidate (clear) the schema cache.

    Use this endpoint when database schema has changed and you need
    to force regeneration of the schema metadata.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    **Returns:**
    ```json
    {
      "message": "Schema cache invalidated successfully",
      "cache_entries_cleared": 2
    }
    ```
    """
    try:
        cache_entries = len(_schema_cache)
        _invalidate_schema_cache()

        return {
            "message": "Schema cache invalidated successfully",
            "cache_entries_cleared": cache_entries
        }

    except Exception as e:
        logger.exception('Error invalidating schema cache')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error invalidating cache: {str(e)}'
        )
