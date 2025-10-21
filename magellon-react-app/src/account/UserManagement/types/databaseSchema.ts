/**
 * Database Schema Types
 *
 * TypeScript interfaces for the database schema returned by GET /db/schema/full
 * Used for building criteria expressions in permission management.
 *
 * Auto-generated from backend schema introspection service.
 */

// Field Types
export type FieldType =
  | 'uuid'
  | 'string'
  | 'text'
  | 'integer'
  | 'decimal'
  | 'boolean'
  | 'datetime'
  | 'date'
  | 'time'
  | 'json';

export type ReferenceType = 'user' | 'entity' | null;

export type EntityCategory = 'core' | 'equipment' | 'security' | 'other';

// Foreign Key Info
export interface ForeignKeyInfo {
  table: string;
  column: string;
  entity: string;
  display_field: string;
}

// Field Definition
export interface FieldDefinition {
  name: string;
  column_name: string;
  caption: string;
  description: string;
  type: FieldType;
  python_type: string;
  sql_type: string;
  nullable: boolean;
  primary_key: boolean;
  foreign_key: ForeignKeyInfo | null;
  default_value: string | null;
  max_length: number | null;
  searchable: boolean;
  sortable: boolean;
  filterable: boolean;
  display_in_list: boolean;
  display_order: number;
  reference_type: ReferenceType;
}

// Relationship Definition
export interface RelationshipDefinition {
  name: string;
  type: 'one-to-many' | 'many-to-one' | 'many-to-many';
  target_entity: string;
  foreign_key_field: string | null;
  target_field: string | null;
}

// Entity Schema
export interface EntitySchema {
  name: string;
  table_name: string;
  caption: string;
  description: string;
  category: EntityCategory;
  permissions_enabled: boolean;
  fields: FieldDefinition[];
  relationships: RelationshipDefinition[];
}

// Operator Definition
export interface OperatorDefinition {
  id: string;
  symbol: string;
  label: string;
  applies_to: FieldType[];
  example: string;
  requires_value: boolean;
  value_type?: 'single' | 'list';
}

// Function Property
export interface FunctionProperty {
  name: string;
  type: string;
  description?: string;
}

// Function Definition
export interface FunctionDefinition {
  name: string;
  syntax: string;
  returns: string;
  description: string;
  example: string;
  category: string;
  properties?: FunctionProperty[];
}

// Logical Operator
export interface LogicalOperator {
  id: string;
  symbol: string;
  label: string;
  example: string;
}

// Example Criteria
export interface ExampleCriteria {
  use_case: string;
  entity: string;
  criteria: string;
  description: string;
  complexity: 'simple' | 'medium' | 'complex';
}

// Schema Metadata
export interface SchemaMetadata {
  generated_at: string;
  version: string;
  total_entities: number;
  include_system: boolean;
  cache_key: string;
}

// Complete Database Schema
export interface DatabaseSchema {
  entities: Record<string, EntitySchema>;
  operators: OperatorDefinition[];
  logical_operators: LogicalOperator[];
  functions: FunctionDefinition[];
  examples: ExampleCriteria[];
  metadata: SchemaMetadata;
}

// Criteria Expression Types
export interface CriteriaCondition {
  field: string;
  operator: string;
  value: any;
  valueType?: 'literal' | 'function' | 'reference';
}

export interface CriteriaGroup {
  logicalOperator: 'AND' | 'OR';
  conditions: (CriteriaCondition | CriteriaGroup)[];
}

// Helper type for building criteria
export type CriteriaExpression = CriteriaCondition | CriteriaGroup;

// Field Value Option (for dropdowns)
export interface FieldValueOption {
  value: string;
  label: string;
  description?: string | null;
}

export interface FieldValueOptions {
  field: string;
  entity: string;
  options: FieldValueOption[];
  total_count: number;
  has_more: boolean;
}
