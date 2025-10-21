/**
 * Criteria Builder Component
 *
 * Visual builder for XAF-style criteria expressions.
 * Allows users to build record-level permission filters using database schema.
 *
 * Example output:
 * - [user_id] = CurrentUserId()
 * - [owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()
 * - [status] = 'active' AND [user_id] = CurrentUserId()
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  IconButton,
  Typography,
  Paper,
  Autocomplete,
  Chip,
  Alert,
  Tooltip,
  Grid,
} from '@mui/material';
import {
  Add,
  Delete,
  Code,
  Info,
  Refresh,
} from '@mui/icons-material';
import { DatabaseSchema, FieldDefinition, OperatorDefinition } from '../types/databaseSchema';

interface Condition {
  id: string;
  field: string;
  operator: string;
  value: string;
  valueType: 'literal' | 'function';
}

interface CriteriaBuilderProps {
  schema: DatabaseSchema;
  entityName: string;
  initialCriteria?: string;
  onChange: (criteria: string) => void;
}

export default function CriteriaBuilder({
  schema,
  entityName,
  initialCriteria = '',
  onChange,
}: CriteriaBuilderProps) {
  const [conditions, setConditions] = useState<Condition[]>([]);
  const [logicalOperator, setLogicalOperator] = useState<'AND' | 'OR'>('AND');
  const [showRaw, setShowRaw] = useState(false);
  const [rawCriteria, setRawCriteria] = useState('');

  const entity = schema.entities[entityName];

  useEffect(() => {
    // Initialize with one empty condition if no initial criteria
    if (!initialCriteria && conditions.length === 0) {
      addCondition();
    } else if (initialCriteria) {
      // Try to parse initial criteria
      setRawCriteria(initialCriteria);
    }
  }, []);

  useEffect(() => {
    // Generate criteria string when conditions change
    const criteria = generateCriteriaString();
    setRawCriteria(criteria);
    onChange(criteria);
  }, [conditions, logicalOperator]);

  const addCondition = () => {
    const newCondition: Condition = {
      id: Date.now().toString(),
      field: '',
      operator: 'eq',
      value: '',
      valueType: 'literal',
    };
    setConditions([...conditions, newCondition]);
  };

  const removeCondition = (id: string) => {
    setConditions(conditions.filter((c) => c.id !== id));
  };

  const updateCondition = (
    id: string,
    updates: Partial<Condition>
  ) => {
    setConditions(
      conditions.map((c) => (c.id === id ? { ...c, ...updates } : c))
    );
  };

  const generateCriteriaString = (): string => {
    if (conditions.length === 0) return '';

    const conditionStrings = conditions
      .filter((c) => c.field && c.operator)
      .map((c) => {
        const field = `[${c.field}]`;
        const op = schema.operators.find((o) => o.id === c.operator);

        if (!op) return '';

        // Handle operators that don't require values
        if (!op.requires_value) {
          return `${field} ${op.symbol}`;
        }

        // Handle function values
        if (c.valueType === 'function') {
          return `${field} ${op.symbol} ${c.value}`;
        }

        // Handle list operators (IN, NOT IN)
        if (op.value_type === 'list') {
          return `${field} ${op.symbol} (${c.value})`;
        }

        // Handle regular values
        const fieldDef = entity?.fields.find((f) => f.name === c.field);
        const needsQuotes =
          fieldDef &&
          (fieldDef.type === 'string' || fieldDef.type === 'text' || fieldDef.type === 'datetime' || fieldDef.type === 'date');

        const value = needsQuotes ? `'${c.value}'` : c.value;
        return `${field} ${op.symbol} ${value}`;
      })
      .filter((s) => s !== '');

    return conditionStrings.join(` ${logicalOperator} `);
  };

  const getApplicableOperators = (fieldName: string): OperatorDefinition[] => {
    if (!entity) return [];

    const field = entity.fields.find((f) => f.name === fieldName);
    if (!field) return schema.operators;

    return schema.operators.filter(
      (op) =>
        op.applies_to.includes('all') || op.applies_to.includes(field.type)
    );
  };

  const getFieldSuggestions = (fieldName: string): string[] => {
    if (!entity || !fieldName) return [];

    const field = entity.fields.find((f) => f.name === fieldName);
    if (!field || !field.foreign_key) return [];

    // For foreign key fields, suggest function
    if (field.reference_type === 'user') {
      return ['CurrentUserId()', "CurrentUser().Oid"];
    }

    return [];
  };

  const renderCondition = (condition: Condition, index: number) => {
    const applicableOperators = getApplicableOperators(condition.field);
    const selectedOp = schema.operators.find((o) => o.id === condition.operator);
    const field = entity?.fields.find((f) => f.name === condition.field);
    const suggestions = getFieldSuggestions(condition.field);

    return (
      <Paper key={condition.id} sx={{ p: 2, mb: 2, bgcolor: 'background.default' }}>
        <Grid container spacing={2} alignItems="center">
          {/* Condition Number */}
          <Grid item xs={12} sm={0.5}>
            <Typography variant="body2" color="text.secondary">
              {index + 1}.
            </Typography>
          </Grid>

          {/* Field Selector */}
          <Grid item xs={12} sm={3}>
            <Autocomplete
              options={entity?.fields || []}
              getOptionLabel={(option) => option.caption || option.name}
              value={entity?.fields.find((f) => f.name === condition.field) || null}
              onChange={(_, newValue) => {
                updateCondition(condition.id, {
                  field: newValue?.name || '',
                  value: '', // Reset value when field changes
                });
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Field"
                  size="small"
                  required
                />
              )}
              renderOption={(props, option) => (
                <li {...props} key={option.name}>
                  <Box>
                    <Typography variant="body2">{option.caption}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {option.name} ({option.type})
                    </Typography>
                  </Box>
                </li>
              )}
            />
          </Grid>

          {/* Operator Selector */}
          <Grid item xs={12} sm={2.5}>
            <FormControl fullWidth size="small">
              <InputLabel>Operator</InputLabel>
              <Select
                value={condition.operator}
                onChange={(e) =>
                  updateCondition(condition.id, { operator: e.target.value })
                }
                label="Operator"
              >
                {applicableOperators.map((op) => (
                  <MenuItem key={op.id} value={op.id}>
                    <Tooltip title={op.example} placement="right">
                      <span>
                        {op.symbol} - {op.label}
                      </span>
                    </Tooltip>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Value Input */}
          {selectedOp && selectedOp.requires_value && (
            <Grid item xs={12} sm={5}>
              <Autocomplete
                freeSolo
                options={suggestions}
                value={condition.value}
                onChange={(_, newValue) => {
                  const isFunctionValue = newValue?.includes('()') || false;
                  updateCondition(condition.id, {
                    value: newValue || '',
                    valueType: isFunctionValue ? 'function' : 'literal',
                  });
                }}
                onInputChange={(_, newValue) => {
                  const isFunctionValue = newValue?.includes('()') || false;
                  updateCondition(condition.id, {
                    value: newValue || '',
                    valueType: isFunctionValue ? 'function' : 'literal',
                  });
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Value"
                    size="small"
                    required
                    placeholder={
                      field?.reference_type === 'user'
                        ? 'CurrentUserId() or a value'
                        : 'Enter value'
                    }
                    helperText={
                      selectedOp.value_type === 'list'
                        ? "Enter values separated by commas: 'val1', 'val2'"
                        : undefined
                    }
                  />
                )}
              />
            </Grid>
          )}

          {/* Delete Button */}
          <Grid item xs={12} sm={1}>
            <Tooltip title="Remove condition">
              <IconButton
                onClick={() => removeCondition(condition.id)}
                color="error"
                size="small"
              >
                <Delete />
              </IconButton>
            </Tooltip>
          </Grid>
        </Grid>
      </Paper>
    );
  };

  if (!entity) {
    return (
      <Alert severity="error">
        Entity "{entityName}" not found in schema
      </Alert>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          Criteria Builder - {entity.caption}
        </Typography>
        <Tooltip title="Toggle raw criteria view">
          <IconButton onClick={() => setShowRaw(!showRaw)} size="small">
            <Code />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Raw Criteria View */}
      {showRaw && (
        <Alert severity="info" icon={<Info />} sx={{ mb: 2 }}>
          <TextField
            fullWidth
            multiline
            rows={2}
            value={rawCriteria}
            onChange={(e) => setRawCriteria(e.target.value)}
            onBlur={() => onChange(rawCriteria)}
            label="Raw Criteria Expression"
            helperText="You can manually edit the criteria here"
            variant="outlined"
            size="small"
          />
        </Alert>
      )}

      {/* Logical Operator Selector (only show if multiple conditions) */}
      {conditions.length > 1 && (
        <Box sx={{ mb: 2 }}>
          <FormControl size="small">
            <InputLabel>Join conditions with</InputLabel>
            <Select
              value={logicalOperator}
              onChange={(e) => setLogicalOperator(e.target.value as 'AND' | 'OR')}
              label="Join conditions with"
            >
              <MenuItem value="AND">AND (all must match)</MenuItem>
              <MenuItem value="OR">OR (any can match)</MenuItem>
            </Select>
          </FormControl>
        </Box>
      )}

      {/* Conditions */}
      <Box sx={{ mb: 2 }}>
        {conditions.map((condition, index) => renderCondition(condition, index))}
      </Box>

      {/* Add Condition Button */}
      <Button
        startIcon={<Add />}
        onClick={addCondition}
        variant="outlined"
        size="small"
      >
        Add Condition
      </Button>

      {/* Examples */}
      <Box sx={{ mt: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Examples:
        </Typography>
        {schema.examples
          .filter((ex) => ex.entity === entityName)
          .map((ex, idx) => (
            <Chip
              key={idx}
              label={ex.criteria}
              size="small"
              sx={{ mr: 1, mb: 1 }}
              onClick={() => {
                setRawCriteria(ex.criteria);
                onChange(ex.criteria);
              }}
              clickable
            />
          ))}
      </Box>

      {/* Generated Criteria Preview */}
      {!showRaw && rawCriteria && (
        <Alert severity="success" sx={{ mt: 2 }}>
          <Typography variant="caption" component="pre">
            {rawCriteria}
          </Typography>
        </Alert>
      )}
    </Box>
  );
}
