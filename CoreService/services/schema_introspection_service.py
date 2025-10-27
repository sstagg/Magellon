"""
Schema Introspection Service

Provides database schema metadata for frontend permission criteria building.
Introspects SQLAlchemy models to generate JSON schema.

Based on XAF security system pattern.
"""
from typing import List, Dict, Optional, Any
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from models.sqlalchemy_models import (
    Base, Msession, Image, Camera, Microscope, Project, Site,
    Atlas, SysSecUser, SysSecRole
)
import logging

logger = logging.getLogger(__name__)


class SchemaIntrospectionService:
    """
    Service to introspect database schema and provide metadata for frontend.
    """

    # Mapping of entity names to SQLAlchemy models
    ENTITY_MAP = {
        'msession': Msession,
        'image': Image,
        'camera': Camera,
        'microscope': Microscope,
        'project': Project,
        'site': Site,
        'atlas': Atlas,
        'sys_sec_user': SysSecUser,
        'sys_sec_role': SysSecRole,
    }

    # Entity categories for UI organization
    ENTITY_CATEGORIES = {
        'msession': {'category': 'core', 'caption': 'Microscopy Session', 'icon': 'microscope'},
        'image': {'category': 'core', 'caption': 'Image', 'icon': 'image'},
        'camera': {'category': 'equipment', 'caption': 'Camera', 'icon': 'camera'},
        'microscope': {'category': 'equipment', 'caption': 'Microscope', 'icon': 'biotech'},
        'project': {'category': 'core', 'caption': 'Project', 'icon': 'folder'},
        'site': {'category': 'core', 'caption': 'Site', 'icon': 'location_on'},
        'atlas': {'category': 'core', 'caption': 'Atlas', 'icon': 'map'},
        'sys_sec_user': {'category': 'security', 'caption': 'User', 'icon': 'person'},
        'sys_sec_role': {'category': 'security', 'caption': 'Role', 'icon': 'security'},
    }

    # SQL type to JSON type mapping
    TYPE_MAP = {
        'BINARY': 'uuid',
        'VARCHAR': 'string',
        'LONGTEXT': 'text',
        'INTEGER': 'integer',
        'BIGINT': 'integer',
        'INT': 'integer',
        'SMALLINT': 'integer',
        'DECIMAL': 'decimal',
        'DOUBLE': 'decimal',
        'FLOAT': 'decimal',
        'BIT': 'boolean',
        'DATETIME': 'datetime',
        'DATE': 'date',
        'TIME': 'time',
        'JSON': 'json',
    }

    @classmethod
    def get_all_entities(
        cls,
        include_system: bool = False,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of all available entities in the system.

        Args:
            include_system: Include system tables (default: False)
            category: Filter by category (core/equipment/security/all)

        Returns:
            List of entity metadata dictionaries
        """
        entities = []

        for entity_name, entity_class in cls.ENTITY_MAP.items():
            # Skip system tables if not requested
            if not include_system and entity_name.startswith('sys_sec'):
                continue

            # Get category info
            cat_info = cls.ENTITY_CATEGORIES.get(entity_name, {
                'category': 'other',
                'caption': entity_name.replace('_', ' ').title(),
                'icon': 'table_chart'
            })

            # Filter by category if specified
            if category and category != 'all' and cat_info['category'] != category:
                continue

            entity = {
                'name': entity_name,
                'table_name': entity_class.__tablename__,
                'caption': cat_info['caption'],
                'description': cls._get_entity_description(entity_class),
                'category': cat_info['category'],
                'icon': cat_info['icon'],
                'permissions_enabled': True
            }
            entities.append(entity)

        return sorted(entities, key=lambda x: (x['category'], x['caption']))

    @classmethod
    def get_entity_schema(cls, entity_name: str) -> Dict[str, Any]:
        """
        Get detailed schema for a specific entity.

        Args:
            entity_name: Name of the entity (e.g., 'msession', 'image')

        Returns:
            Entity schema dictionary with fields and relationships

        Raises:
            ValueError: If entity not found
        """
        entity_class = cls.ENTITY_MAP.get(entity_name)
        if not entity_class:
            raise ValueError(f"Entity '{entity_name}' not found")

        # Get category info
        cat_info = cls.ENTITY_CATEGORIES.get(entity_name, {
            'category': 'other',
            'caption': entity_name.replace('_', ' ').title(),
            'icon': 'table_chart'
        })

        # Introspect columns
        mapper = inspect(entity_class)
        fields = []

        for column in mapper.columns:
            field = cls._build_field_metadata(column, entity_class)
            fields.append(field)

        # Get relationships
        relationships = cls._get_relationships(entity_class)

        return {
            'entity': {
                'name': entity_name,
                'table_name': entity_class.__tablename__,
                'caption': cat_info['caption'],
                'description': cls._get_entity_description(entity_class),
                'category': cat_info['category'],
                'permissions_enabled': True,
                'fields': fields,
                'relationships': relationships
            }
        }

    @classmethod
    def _build_field_metadata(cls, column, entity_class) -> Dict[str, Any]:
        """
        Build metadata dictionary for a single field/column.

        Args:
            column: SQLAlchemy column object
            entity_class: The entity class

        Returns:
            Field metadata dictionary
        """
        # Map SQL type to JSON type
        sql_type = str(column.type).split('(')[0]
        json_type = cls.TYPE_MAP.get(sql_type, 'string')

        # Special handling for binary(16) = UUID
        if 'BINARY' in str(column.type) and '16' in str(column.type):
            json_type = 'uuid'

        # Get foreign key info
        foreign_key = cls._get_foreign_key_info(column)

        # Determine if this is a reference field
        reference_type = None
        if foreign_key:
            # Check if it's a user reference
            if 'user' in column.name.lower() or foreign_key['table'] == 'sys_sec_user':
                reference_type = 'user'
            # Check if it's an entity reference
            elif foreign_key['table'] in cls.ENTITY_MAP:
                reference_type = 'entity'

        # Get max length for strings
        max_length = None
        if 'VARCHAR' in str(column.type):
            try:
                max_length = int(str(column.type).split('(')[1].split(')')[0])
            except:
                pass

        # Build caption from column name
        caption = cls._build_caption(column.name)

        return {
            'name': column.name,
            'column_name': column.name,
            'caption': caption,
            'description': cls._get_field_description(column.name),
            'type': json_type,
            'python_type': type(column.type).__name__,
            'sql_type': str(column.type),
            'nullable': column.nullable,
            'primary_key': column.primary_key,
            'foreign_key': foreign_key,
            'default_value': str(column.default.arg) if column.default else None,
            'max_length': max_length,
            'searchable': cls._is_searchable(column, json_type),
            'sortable': True,
            'filterable': True,
            'display_in_list': cls._should_display_in_list(column),
            'display_order': cls._get_display_order(column),
            'reference_type': reference_type
        }

    @classmethod
    def _get_foreign_key_info(cls, column) -> Optional[Dict[str, str]]:
        """
        Extract foreign key information from a column.

        Args:
            column: SQLAlchemy column object

        Returns:
            Foreign key metadata or None
        """
        if column.foreign_keys:
            fk = list(column.foreign_keys)[0]
            target_table = fk.column.table.name
            target_column = fk.column.name

            # Find entity name from table name
            entity_name = None
            for ent_name, ent_class in cls.ENTITY_MAP.items():
                if ent_class.__tablename__ == target_table:
                    entity_name = ent_name
                    break

            # Determine display field
            display_field = 'name'
            if target_table == 'sys_sec_user':
                display_field = 'USERNAME'
            elif target_table == 'sys_sec_role':
                display_field = 'Name'

            return {
                'table': target_table,
                'column': target_column,
                'entity': entity_name or target_table,
                'display_field': display_field
            }
        return None

    @classmethod
    def _get_relationships(cls, entity_class) -> List[Dict[str, Any]]:
        """
        Get relationship information for an entity.

        Args:
            entity_class: The SQLAlchemy entity class

        Returns:
            List of relationship dictionaries
        """
        relationships = []
        mapper = inspect(entity_class)

        for rel in mapper.relationships:
            relationship = {
                'name': rel.key,
                'type': 'one-to-many' if rel.uselist else 'many-to-one',
                'target_entity': rel.entity.class_.__name__.lower(),
                'foreign_key_field': None,
                'target_field': None
            }
            relationships.append(relationship)

        return relationships

    @classmethod
    def _get_entity_description(cls, entity_class) -> str:
        """
        Get description for an entity.

        Args:
            entity_class: The SQLAlchemy entity class

        Returns:
            Description string
        """
        descriptions = {
            'Msession': 'Microscopy imaging session grouping images',
            'Image': 'Electron microscopy images',
            'Camera': 'Camera equipment used for imaging',
            'Microscope': 'Microscope equipment',
            'Project': 'Research projects',
            'Site': 'Physical locations/sites',
            'Atlas': 'Image atlases',
            'SysSecUser': 'System users',
            'SysSecRole': 'User roles'
        }
        return descriptions.get(entity_class.__name__, '')

    @classmethod
    def _get_field_description(cls, field_name: str) -> str:
        """
        Generate description for a field based on its name.

        Args:
            field_name: The field name

        Returns:
            Description string
        """
        descriptions = {
            'oid': 'Unique identifier',
            'name': 'Name',
            'user_id': 'Associated user',
            'project_id': 'Associated project',
            'session_id': 'Associated session',
            'camera_id': 'Camera used',
            'microscope_id': 'Microscope used',
            'start_on': 'Start date/time',
            'end_on': 'End date/time',
            'created_date': 'Creation date',
            'created_by': 'Created by user',
            'last_modified_date': 'Last modification date',
            'last_modified_by': 'Last modified by user',
            'deleted_date': 'Deletion date',
            'deleted_by': 'Deleted by user',
            'OptimisticLockField': 'Concurrency control version',
            'GCRecord': 'Soft delete marker (NULL = active)',
        }
        return descriptions.get(field_name, '')

    @classmethod
    def _build_caption(cls, field_name: str) -> str:
        """
        Build user-friendly caption from field name.

        Args:
            field_name: The field name

        Returns:
            Caption string
        """
        # Special cases
        captions = {
            'oid': 'ID',
            'user_id': 'Owner',
            'project_id': 'Project',
            'session_id': 'Session',
            'camera_id': 'Camera',
            'microscope_id': 'Microscope',
            'start_on': 'Start Date',
            'end_on': 'End Date',
            'USERNAME': 'Username',
            'PASSWORD': 'Password',
            'ACTIVE': 'Active',
        }

        if field_name in captions:
            return captions[field_name]

        # Convert snake_case to Title Case
        return field_name.replace('_', ' ').title()

    @classmethod
    def _is_searchable(cls, column, json_type: str) -> bool:
        """
        Determine if a field is searchable.

        Args:
            column: SQLAlchemy column
            json_type: The JSON type

        Returns:
            True if searchable
        """
        # Primary keys and foreign keys are searchable
        if column.primary_key or column.foreign_keys:
            return True

        # String fields are searchable
        if json_type in ['string', 'text']:
            return True

        # Common name fields
        if 'name' in column.name.lower():
            return True

        return False

    @classmethod
    def _should_display_in_list(cls, column) -> bool:
        """
        Determine if a field should be displayed in list views.

        Args:
            column: SQLAlchemy column

        Returns:
            True if should display in lists
        """
        # Don't show system fields
        system_fields = ['OptimisticLockField', 'GCRecord', 'ObjectType', 'omid', 'ouid', 'sync_status']
        if column.name in system_fields:
            return False

        # Don't show password fields
        if 'password' in column.name.lower():
            return False

        # Don't show binary primary keys (UUIDs)
        if column.primary_key and 'BINARY' in str(column.type):
            return False

        # Don't show deleted/audit fields
        if column.name in ['deleted_date', 'deleted_by']:
            return False

        return True

    @classmethod
    def _get_display_order(cls, column) -> int:
        """
        Get display order for a field.

        Args:
            column: SQLAlchemy column

        Returns:
            Display order (lower = earlier)
        """
        # Primary keys first (but hidden)
        if column.primary_key:
            return 1

        # Name fields second
        if 'name' in column.name.lower():
            return 2

        # Description fields
        if 'description' in column.name.lower():
            return 10

        # Dates
        if 'date' in column.name.lower():
            return 20

        # Everything else
        return 15


    @classmethod
    def get_field_value_options(
        cls,
        db: Session,
        entity_name: str,
        field_name: str,
        search: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get possible values for a field (for dropdowns, autocomplete).

        Args:
            db: Database session
            entity_name: Entity name
            field_name: Field name
            search: Optional search term
            limit: Maximum number of options

        Returns:
            Dictionary with options and metadata
        """
        entity_class = cls.ENTITY_MAP.get(entity_name)
        if not entity_class:
            raise ValueError(f"Entity '{entity_name}' not found")

        # Get the column
        mapper = inspect(entity_class)
        matching_columns = [col for col in mapper.columns if col.name == field_name]

        if len(matching_columns) == 0:
            raise ValueError(f"Field '{field_name}' not found in entity '{entity_name}'")

        column = matching_columns[0]

        # Check if it's a foreign key
        fk_info = cls._get_foreign_key_info(column)

        if fk_info:
            # Handle foreign key fields - fetch from related table
            target_entity_class = cls.ENTITY_MAP.get(fk_info['entity'])
            if not target_entity_class:
                return {
                    'field': field_name,
                    'entity': entity_name,
                    'options': [],
                    'total_count': 0,
                    'has_more': False
                }

            # Query the target entity
            query = db.query(target_entity_class)

            # Apply search if provided
            display_field = fk_info['display_field']
            if search and hasattr(target_entity_class, display_field):
                query = query.filter(
                    getattr(target_entity_class, display_field).like(f'%{search}%')
                )

            # Get total count
            total_count = query.count()

            # Limit results
            results = query.limit(limit).all()

            # Build options
            options = []
            for result in results:
                option = {
                    'value': str(getattr(result, 'oid' if hasattr(result, 'oid') else 'Oid')),
                    'label': str(getattr(result, display_field, '')),
                    'description': getattr(result, 'description', None) if hasattr(result, 'description') else None
                }
                options.append(option)
        else:
            # Handle non-foreign-key fields - fetch distinct values from this field
            field_attr = getattr(entity_class, field_name)

            # Query distinct values - filter out NULL values first
            query = db.query(field_attr).distinct().filter(field_attr.isnot(None))

            # Apply search if provided
            if search:
                query = query.filter(field_attr.like(f'%{search}%'))

            # Order by the field
            query = query.order_by(field_attr)

            # Get results first
            results = query.limit(limit).all()

            # Build options and filter out empty strings
            options = []
            for (value,) in results:
                # Skip empty strings
                if value and str(value).strip():
                    option = {
                        'value': str(value),
                        'label': str(value),
                        'description': None
                    }
                    options.append(option)

            # Total count
            total_count = len(options)

        return {
            'field': field_name,
            'entity': entity_name,
            'options': options,
            'total_count': total_count,
            'has_more': total_count > limit
        }
