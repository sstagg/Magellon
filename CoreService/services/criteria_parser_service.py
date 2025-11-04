"""
Criteria Parser Service

Parses  criteria expressions and converts them to SQLAlchemy filters.
Supports CurrentUserId() and CurrentUser() functions.

Based on  criteria syntax:
- [field] = CurrentUserId()
- [field] = 'value'
- [field1] = CurrentUserId() AND [field2] = 'active'
- [field1] = CurrentUserId() OR [field2] = CurrentUserId()
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import and_, or_, not_
from sqlalchemy.sql import ColumnElement
import logging

logger = logging.getLogger(__name__)


class CriteriaParserService:
    """
    Parses  criteria expressions into SQLAlchemy filters.
    """

    # Supported operators
    OPERATORS = {
        '=': '__eq__',
        '!=': '__ne__',
        '>': '__gt__',
        '>=': '__ge__',
        '<': '__lt__',
        '<=': '__le__',
        'IN': 'in_',
        'NOT IN': 'not_in',
        'LIKE': 'like',
        'IS NULL': 'is_',
        'IS NOT NULL': 'isnot',
    }

    @classmethod
    def parse(
        cls,
        criteria: str,
        entity_class: Any,
        current_user_id: UUID,
        current_user: Optional[Dict[str, Any]] = None
    ) -> Optional[ColumnElement]:
        """
        Parse criteria expression and return SQLAlchemy filter.

        Args:
            criteria:  criteria expression
            entity_class: SQLAlchemy entity class
            current_user_id: Current user's UUID
            current_user: Current user object (for CurrentUser() function)

        Returns:
            SQLAlchemy filter expression or None

        Examples:
            "[user_id] = CurrentUserId()"
            "[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()"
            "[status] = 'active'"
        """
        if not criteria or not criteria.strip():
            return None

        try:
            # Replace functions with actual values
            processed = cls._replace_functions(criteria, current_user_id, current_user)

            # Parse the expression
            filter_expr = cls._parse_expression(processed, entity_class)

            return filter_expr

        except Exception as e:
            logger.error(f"Failed to parse criteria: {criteria}. Error: {e}")
            raise ValueError(f"Invalid criteria expression: {str(e)}")

    @classmethod
    def _replace_functions(
        cls,
        criteria: str,
        current_user_id: UUID,
        current_user: Optional[Dict[str, Any]]
    ) -> str:
        """
        Replace function calls with actual values.

        Args:
            criteria: Original criteria string
            current_user_id: Current user's UUID
            current_user: Current user object

        Returns:
            Processed criteria string with functions replaced
        """
        result = criteria

        # Replace CurrentUserId()
        result = result.replace('CurrentUserId()', f"'{str(current_user_id)}'")

        # Replace CurrentUser().Property
        if current_user:
            # Find all CurrentUser().Property patterns
            pattern = r'CurrentUser\(\)\.(\w+)'
            matches = re.findall(pattern, result)
            for property_name in matches:
                # Get property value from current_user dict
                value = current_user.get(property_name)
                if value is not None:
                    if isinstance(value, str):
                        replacement = f"'{value}'"
                    elif isinstance(value, UUID):
                        replacement = f"'{str(value)}'"
                    else:
                        replacement = str(value)

                    result = result.replace(f'CurrentUser().{property_name}', replacement)

        return result

    @classmethod
    def _parse_expression(cls, expression: str, entity_class: Any) -> Optional[ColumnElement]:
        """
        Parse a logical expression (with AND/OR).

        Args:
            expression: Processed expression string
            entity_class: SQLAlchemy entity class

        Returns:
            SQLAlchemy filter expression
        """
        # Handle AND/OR operators
        if ' AND ' in expression:
            parts = cls._split_by_operator(expression, ' AND ')
            filters = [cls._parse_expression(part, entity_class) for part in parts]
            return and_(*[f for f in filters if f is not None])

        if ' OR ' in expression:
            parts = cls._split_by_operator(expression, ' OR ')
            filters = [cls._parse_expression(part, entity_class) for part in parts]
            return or_(*[f for f in filters if f is not None])

        # Parse single condition
        return cls._parse_condition(expression.strip(), entity_class)

    @classmethod
    def _split_by_operator(cls, expression: str, operator: str) -> List[str]:
        """
        Split expression by logical operator, respecting parentheses.

        Args:
            expression: Expression to split
            operator: Operator to split by (e.g., ' AND ', ' OR ')

        Returns:
            List of expression parts
        """
        parts = []
        current = []
        depth = 0

        tokens = expression.split(operator)
        for token in tokens:
            # Count parentheses
            depth += token.count('(') - token.count(')')

            if depth == 0:
                current.append(token)
                parts.append(operator.join(current))
                current = []
            else:
                current.append(token)

        if current:
            parts.append(operator.join(current))

        return parts

    @classmethod
    def _parse_condition(cls, condition: str, entity_class: Any) -> Optional[ColumnElement]:
        """
        Parse a single condition (e.g., "[field] = 'value'").

        Args:
            condition: Condition string
            entity_class: SQLAlchemy entity class

        Returns:
            SQLAlchemy filter expression
        """
        # Remove outer parentheses if present
        condition = condition.strip()
        if condition.startswith('(') and condition.endswith(')'):
            return cls._parse_expression(condition[1:-1], entity_class)

        # Extract field, operator, and value
        field_name, operator, value = cls._extract_condition_parts(condition)

        if not field_name:
            return None

        # Get the column from entity class
        if not hasattr(entity_class, field_name):
            raise ValueError(f"Field '{field_name}' not found in entity")

        column = getattr(entity_class, field_name)

        # Build filter based on operator
        if operator == '=' or operator == '==':
            return column == cls._parse_value(value)
        elif operator == '!=':
            return column != cls._parse_value(value)
        elif operator == '>':
            return column > cls._parse_value(value)
        elif operator == '>=':
            return column >= cls._parse_value(value)
        elif operator == '<':
            return column < cls._parse_value(value)
        elif operator == '<=':
            return column <= cls._parse_value(value)
        elif operator.upper() == 'IN':
            values = cls._parse_in_list(value)
            return column.in_(values)
        elif operator.upper() == 'NOT IN':
            values = cls._parse_in_list(value)
            return column.not_in(values)
        elif operator.upper() == 'LIKE':
            return column.like(cls._parse_value(value))
        elif operator.upper() == 'IS NULL':
            return column.is_(None)
        elif operator.upper() == 'IS NOT NULL':
            return column.isnot(None)
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    @classmethod
    def _extract_condition_parts(cls, condition: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract field name, operator, and value from a condition.

        Args:
            condition: Condition string (e.g., "[field] = 'value'")

        Returns:
            Tuple of (field_name, operator, value)
        """
        #  format: [field] = 'value' or field = 'value'
        # Extract field name (with or without brackets)
        field_match = re.match(r'\[?(\w+)\]?\s*(.*)', condition)
        if not field_match:
            return None, None, None

        field_name = field_match.group(1)
        rest = field_match.group(2).strip()

        # Extract operator and value
        # Try multi-character operators first
        for op in ['IS NOT NULL', 'IS NULL', 'NOT IN', '!=', '>=', '<=', 'IN', 'LIKE']:
            if rest.upper().startswith(op):
                operator = op
                value = rest[len(op):].strip()
                return field_name, operator, value

        # Try single-character operators
        for op in ['=', '>', '<']:
            if rest.startswith(op):
                operator = op
                value = rest[len(op):].strip()
                return field_name, operator, value

        return None, None, None

    @classmethod
    def _parse_value(cls, value: str) -> Any:
        """
        Parse a value from string to appropriate Python type.

        Args:
            value: Value string

        Returns:
            Parsed value
        """
        if not value:
            return None

        value = value.strip()

        # Remove quotes if present
        if (value.startswith("'") and value.endswith("'")) or \
           (value.startswith('"') and value.endswith('"')):
            value = value[1:-1]

        # Try to parse as UUID
        try:
            return UUID(value)
        except:
            pass

        # Try to parse as number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except:
            pass

        # Try to parse as boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False

        # Return as string
        return value

    @classmethod
    def _parse_in_list(cls, value: str) -> List[Any]:
        """
        Parse IN list: ('value1', 'value2', 'value3')

        Args:
            value: IN list string

        Returns:
            List of parsed values
        """
        # Remove outer parentheses
        value = value.strip()
        if value.startswith('(') and value.endswith(')'):
            value = value[1:-1]

        # Split by comma
        items = []
        for item in value.split(','):
            items.append(cls._parse_value(item.strip()))

        return items

    @classmethod
    def validate(
        cls,
        criteria: str,
        entity_class: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a criteria expression without executing it.

        Args:
            criteria: Criteria expression to validate
            entity_class: SQLAlchemy entity class

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to parse with dummy values
            dummy_user_id = UUID('00000000-0000-0000-0000-000000000000')
            cls.parse(criteria, entity_class, dummy_user_id, {})
            return True, None
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_example_criteria(cls) -> List[Dict[str, str]]:
        """
        Get example criteria expressions for documentation/UI.

        Returns:
            List of example dictionaries
        """
        return [
            {
                'use_case': 'Users can only see their own records',
                'criteria': '[user_id] = CurrentUserId()',
                'description': 'Filter where user_id equals the current user ID'
            },
            {
                'use_case': 'Users can see their own records OR records assigned to them',
                'criteria': '[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()',
                'description': 'Filter where owner or assigned user is current user'
            },
            {
                'use_case': 'Users can only see active records they own',
                'criteria': '[owner_id] = CurrentUserId() AND [status] = \'active\'',
                'description': 'Filter where owner is current user and status is active'
            },
            {
                'use_case': 'Users can see non-archived records',
                'criteria': '[status] != \'archived\'',
                'description': 'Filter where status is not archived'
            },
            {
                'use_case': 'Users can see records in specific statuses',
                'criteria': '[status] IN (\'draft\', \'pending\', \'active\')',
                'description': 'Filter where status is in the specified list'
            }
        ]
