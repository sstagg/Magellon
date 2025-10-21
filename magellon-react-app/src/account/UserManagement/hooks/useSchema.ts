/**
 * Schema Hook
 *
 * Fetches and caches database schema for criteria building.
 * The schema includes entities, fields, operators, and functions.
 */
import { useState, useEffect } from 'react';
import axios from 'axios';
import { DatabaseSchema } from '../types/databaseSchema';

const SCHEMA_CACHE_KEY = 'magellon_schema_cache';
const SCHEMA_CACHE_TTL = 60 * 60 * 1000; // 1 hour in milliseconds

const API_BASE_URL = 'http://localhost:8000';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

interface CachedSchema {
  data: DatabaseSchema;
  timestamp: number;
}

export function useSchema(includeSystem: boolean = false) {
  const [schema, setSchema] = useState<DatabaseSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSchema();
  }, [includeSystem]);

  const fetchSchema = async () => {
    setLoading(true);
    setError(null);

    try {
      // Check cache first
      const cached = getFromCache();
      if (cached) {
        console.log('Using cached schema data');
        setSchema(cached);
        setLoading(false);
        return;
      }

      // Fetch from API
      console.log('Fetching fresh schema from API');
      const response = await apiClient.get<DatabaseSchema>(
        `/db/schema/full?include_system=${includeSystem}`
      );

      const schemaData = response.data;

      // Cache the response
      saveToCache(schemaData);

      setSchema(schemaData);
    } catch (err: any) {
      console.error('Failed to fetch schema:', err);
      setError(err.response?.data?.detail || 'Failed to fetch database schema');
    } finally {
      setLoading(false);
    }
  };

  const refreshSchema = async () => {
    // Clear cache and fetch fresh
    localStorage.removeItem(SCHEMA_CACHE_KEY);

    try {
      setLoading(true);
      const response = await apiClient.get<DatabaseSchema>(
        `/db/schema/full?include_system=${includeSystem}&force_refresh=true`
      );

      const schemaData = response.data;
      saveToCache(schemaData);
      setSchema(schemaData);
      setError(null);
    } catch (err: any) {
      console.error('Failed to refresh schema:', err);
      setError(err.response?.data?.detail || 'Failed to refresh schema');
    } finally {
      setLoading(false);
    }
  };

  const getFromCache = (): DatabaseSchema | null => {
    try {
      const cached = localStorage.getItem(SCHEMA_CACHE_KEY);
      if (!cached) return null;

      const parsed: CachedSchema = JSON.parse(cached);

      // Check if cache is expired
      const now = Date.now();
      if (now - parsed.timestamp > SCHEMA_CACHE_TTL) {
        console.log('Schema cache expired');
        localStorage.removeItem(SCHEMA_CACHE_KEY);
        return null;
      }

      return parsed.data;
    } catch (error) {
      console.error('Failed to read schema from cache:', error);
      return null;
    }
  };

  const saveToCache = (data: DatabaseSchema) => {
    try {
      const cached: CachedSchema = {
        data,
        timestamp: Date.now(),
      };
      localStorage.setItem(SCHEMA_CACHE_KEY, JSON.stringify(cached));
    } catch (error) {
      console.error('Failed to save schema to cache:', error);
    }
  };

  return {
    schema,
    loading,
    error,
    refreshSchema,
  };
}
