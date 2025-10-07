/**
 * RBAC API Service
 * TypeScript API client for Role-Based Access Control endpoints
 */

import axios, { AxiosInstance } from 'axios';

// Base configuration
const API_BASE_URL =  'http://localhost:8000';

// Create axios instance
const apiClient: AxiosInstance = axios.create({
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

// ==================== TYPE DEFINITIONS ====================

export interface Role {
  oid: string;
  name: string;
  is_administrative: boolean;
  can_edit_model: boolean;
  permission_policy: number;
  tenant_id?: string;
  OptimisticLockField?: number;
  GCRecord?: number;
  ObjectType?: number;
}

export interface CreateRoleRequest {
  name: string;
  is_administrative: boolean;
  can_edit_model: boolean;
  permission_policy: number;
  tenant_id?: string;
}

export interface UpdateRoleRequest {
  oid: string;
  name?: string;
  is_administrative?: boolean;
  can_edit_model?: boolean;
  permission_policy?: number;
}

export interface UserRole {
  oid: string;
  user_id: string;
  role_id: string;
  role_name: string;
  is_administrative: boolean;
  can_edit_model: boolean;
}

export interface AssignRoleRequest {
  user_id: string;
  role_id: string;
}

export interface BulkRoleAssignmentRequest {
  user_ids: string[];
  role_id: string;
}

export interface ActionPermission {
  oid: string;
  action_id: string;
  role_id: string;
  OptimisticLockField?: number;
}

export interface CreateActionPermissionRequest {
  action_id: string;
  role_id: string;
}

export interface NavigationPermission {
  oid: string;
  item_path: string;
  navigate_state: number;
  role_id: string;
  OptimisticLockField?: number;
}

export interface CreateNavigationPermissionRequest {
  item_path: string;
  navigate_state: number;
  role_id: string;
}

export interface TypePermission {
  oid: string;
  target_type: string;
  role_id: string;
  read_state: number;
  write_state: number;
  create_state: number;
  delete_state: number;
  navigate_state: number;
  OptimisticLockField?: number;
}

export interface CreateTypePermissionRequest {
  target_type: string;
  role: string;
  read_state: number;
  write_state: number;
  create_state: number;
  delete_state: number;
  navigate_state: number;
}

export interface PermissionCheckRequest {
  user_id: string;
  permission_type: string;
  resource: string;
  operation?: string;
}

export interface PermissionCheckResponse {
  has_permission: boolean;
  reason?: string;
}

export interface UserPermissionsSummary {
  user_id: string;
  username: string;
  roles: Role[];
  action_permissions: ActionPermission[];
  navigation_permissions: NavigationPermission[];
  is_admin: boolean;
}

export interface RolePermissionsSummary {
  role_id: string;
  role_name: string;
  is_administrative: boolean;
  permissions: {
    actions: string[];
    navigation: Array<{ path: string; allowed: boolean }>;
    types: Array<{
      type: string;
      read: boolean;
      write: boolean;
      create: boolean;
      delete: boolean;
      navigate: boolean;
    }>;
  };
  counts: {
    actions: number;
    navigation: number;
    types: number;
  };
}

export interface BulkPermissionRequest {
  role_id: string;
  permissions: string[];
  permission_type: string;
}

export interface PermissionBatchResponse {
  created_count: number;
  failed_count: number;
  errors?: string[];
}

// ==================== ROLE MANAGEMENT API ====================

export class RoleAPI {
  /**
   * Create a new role
   */
  static async createRole(data: CreateRoleRequest): Promise<Role> {
    const response = await apiClient.post('/db/security/roles/', data);
    return response.data;
  }

  /**
   * Update an existing role
   */
  static async updateRole(data: UpdateRoleRequest): Promise<Role> {
    const response = await apiClient.put('/db/security/roles/', data);
    return response.data;
  }

  /**
   * Get all roles
   */
  static async getRoles(params?: {
    skip?: number;
    limit?: number;
    name?: string;
    tenant_id?: string;
  }): Promise<Role[]> {
    const response = await apiClient.get('/db/security/roles/', { params });
    return response.data;
  }

  /**
   * Get role by ID
   */
  static async getRoleById(roleId: string): Promise<Role> {
    const response = await apiClient.get(`/db/security/roles/${roleId}`);
    return response.data;
  }

  /**
   * Get role by name
   */
  static async getRoleByName(roleName: string): Promise<Role> {
    const response = await apiClient.get(`/db/security/roles/name/${roleName}`);
    return response.data;
  }

  /**
   * Delete role
   */
  static async deleteRole(roleId: string, hardDelete: boolean = false): Promise<void> {
    await apiClient.delete(`/db/security/roles/${roleId}`, {
      params: { hard_delete: hardDelete },
    });
  }

  /**
   * Get users in a role
   */
  static async getRoleUsers(roleId: string): Promise<any> {
    const response = await apiClient.get(`/db/security/roles/${roleId}/users`);
    return response.data;
  }

  /**
   * Get administrative roles
   */
  static async getAdministrativeRoles(): Promise<Role[]> {
    const response = await apiClient.get('/db/security/roles/administrative');
    return response.data;
  }

  /**
   * Get role count
   */
  static async getRoleCount(tenantId?: string): Promise<{ total_roles: number }> {
    const response = await apiClient.get('/db/security/roles/stats/count', {
      params: { tenant_id: tenantId },
    });
    return response.data;
  }

  /**
   * Get role statistics
   */
  static async getRoleStatistics(): Promise<any> {
    const response = await apiClient.get('/db/security/roles/stats/summary');
    return response.data;
  }
}

// ==================== USER-ROLE MANAGEMENT API ====================

export class UserRoleAPI {
  /**
   * Assign a role to a user
   */
  static async assignRole(data: AssignRoleRequest): Promise<any> {
    const response = await apiClient.post('/db/security/user-roles/', {
      user_id: data.user_id,
      role_id: data.role_id,
    });
    return response.data;
  }

  /**
   * Remove a role from a user
   */
  static async removeRole(userId: string, roleId: string): Promise<void> {
    await apiClient.delete(`/db/security/user-roles/user/${userId}/role/${roleId}`);
  }

  /**
   * Get user's roles
   */
  static async getUserRoles(userId: string): Promise<UserRole[]> {
    const response = await apiClient.get(`/db/security/user-roles/user/${userId}/roles`);
    return response.data;
  }

  /**
   * Get role's users
   */
  static async getRoleUsers(roleId: string): Promise<any> {
    const response = await apiClient.get(`/db/security/user-roles/role/${roleId}/users`);
    return response.data;
  }

  /**
   * Bulk assign role to multiple users
   */
  static async bulkAssignRole(data: BulkRoleAssignmentRequest): Promise<any> {
    const response = await apiClient.post('/db/security/user-roles/bulk-assign', data);
    return response.data;
  }

  /**
   * Sync user roles (replace all roles with new list)
   */
  static async syncUserRoles(userId: string, roleIds: string[]): Promise<any> {
    const response = await apiClient.put(`/db/security/user-roles/user/${userId}/sync-roles`, roleIds);
    return response.data;
  }

  /**
   * Remove all roles from a user
   */
  static async removeAllUserRoles(userId: string): Promise<void> {
    await apiClient.delete(`/db/security/user-roles/user/${userId}/roles`);
  }

  /**
   * Check if user has specific role
   */
  static async checkUserHasRole(userId: string, roleName: string): Promise<{ has_role: boolean }> {
    const response = await apiClient.get(`/db/security/user-roles/user/${userId}/has-role/${roleName}`);
    return response.data;
  }

  /**
   * Check if user is admin
   */
  static async checkUserIsAdmin(userId: string): Promise<{ is_admin: boolean }> {
    const response = await apiClient.get(`/db/security/user-roles/user/${userId}/is-admin`);
    return response.data;
  }
}

// ==================== PERMISSION CHECKING API ====================

export class PermissionAPI {
  /**
   * Check generic permission
   */
  static async checkPermission(data: PermissionCheckRequest): Promise<PermissionCheckResponse> {
    const response = await apiClient.post('/db/security/permissions/check', data);
    return response.data;
  }

  /**
   * Get user permissions summary
   */
  static async getUserPermissionsSummary(userId: string): Promise<UserPermissionsSummary> {
    const response = await apiClient.get(`/db/security/permissions/user/${userId}/summary`);
    return response.data;
  }

  /**
   * Check if user is admin
   */
  static async isAdmin(userId: string): Promise<{ is_admin: boolean }> {
    const response = await apiClient.get(`/db/security/permissions/user/${userId}/is-admin`);
    return response.data;
  }

  /**
   * Check action permission
   */
  static async checkActionPermission(
    userId: string,
    actionId: string
  ): Promise<{ has_permission: boolean }> {
    const response = await apiClient.get(
      `/db/security/permissions/user/${userId}/action/${actionId}`
    );
    return response.data;
  }

  /**
   * Check navigation permission
   */
  static async checkNavigationPermission(
    userId: string,
    itemPath: string
  ): Promise<{ has_permission: boolean }> {
    const response = await apiClient.get(`/db/security/permissions/user/${userId}/navigation`, {
      params: { item_path: itemPath },
    });
    return response.data;
  }

  /**
   * Check type permission
   */
  static async checkTypePermission(
    userId: string,
    targetType: string,
    operation: string = 'read'
  ): Promise<{ has_permission: boolean }> {
    const response = await apiClient.get(
      `/db/security/permissions/user/${userId}/type/${targetType}`,
      { params: { operation } }
    );
    return response.data;
  }
}

// ==================== PERMISSION MANAGEMENT API ====================

export class PermissionManagementAPI {
  // ===== Action Permissions =====

  static async createActionPermission(
    data: CreateActionPermissionRequest
  ): Promise<ActionPermission> {
    const response = await apiClient.post('/db/security/permission-management/actions', data);
    return response.data;
  }

  static async getRoleActionPermissions(roleId: string): Promise<ActionPermission[]> {
    const response = await apiClient.get(
      `/db/security/permission-management/actions/role/${roleId}`
    );
    return response.data;
  }

  static async getActionRoles(actionId: string): Promise<any> {
    const response = await apiClient.get(
      `/db/security/permission-management/actions/action/${actionId}`
    );
    return response.data;
  }

  static async deleteActionPermission(permissionId: string): Promise<void> {
    await apiClient.delete(`/db/security/permission-management/actions/${permissionId}`);
  }

  static async bulkCreateActionPermissions(
    data: BulkPermissionRequest
  ): Promise<PermissionBatchResponse> {
    const response = await apiClient.post(
      '/db/security/permission-management/actions/bulk',
      data
    );
    return response.data;
  }

  // ===== Navigation Permissions =====

  static async createNavigationPermission(
    data: CreateNavigationPermissionRequest
  ): Promise<NavigationPermission> {
    const response = await apiClient.post('/db/security/permission-management/navigation', data);
    return response.data;
  }

  static async updateNavigationPermission(
    permissionId: string,
    navigateState: number
  ): Promise<NavigationPermission> {
    const response = await apiClient.put(
      `/db/security/permission-management/navigation/${permissionId}`,
      null,
      { params: { navigate_state: navigateState } }
    );
    return response.data;
  }

  static async getRoleNavigationPermissions(roleId: string): Promise<NavigationPermission[]> {
    const response = await apiClient.get(
      `/db/security/permission-management/navigation/role/${roleId}`
    );
    return response.data;
  }

  static async getPathRoles(itemPath: string): Promise<any> {
    const response = await apiClient.get('/db/security/permission-management/navigation/path', {
      params: { item_path: itemPath },
    });
    return response.data;
  }

  static async deleteNavigationPermission(permissionId: string): Promise<void> {
    await apiClient.delete(`/db/security/permission-management/navigation/${permissionId}`);
  }

  static async bulkCreateNavigationPermissions(
    data: BulkPermissionRequest,
    navigateState: number = 1
  ): Promise<PermissionBatchResponse> {
    const response = await apiClient.post(
      '/db/security/permission-management/navigation/bulk',
      data,
      { params: { navigate_state: navigateState } }
    );
    return response.data;
  }

  // ===== Type Permissions =====

  static async createTypePermission(data: CreateTypePermissionRequest): Promise<TypePermission> {
    const response = await apiClient.post('/db/security/permission-management/types', data);
    return response.data;
  }

  static async updateTypePermission(
    permissionId: string,
    states: {
      read_state?: number;
      write_state?: number;
      create_state?: number;
      delete_state?: number;
      navigate_state?: number;
    }
  ): Promise<TypePermission> {
    const response = await apiClient.put(
      `/db/security/permission-management/types/${permissionId}`,
      null,
      { params: states }
    );
    return response.data;
  }

  static async getRoleTypePermissions(roleId: string): Promise<TypePermission[]> {
    const response = await apiClient.get(
      `/db/security/permission-management/types/role/${roleId}`
    );
    return response.data;
  }

  static async getTypeRoles(targetType: string): Promise<any> {
    const response = await apiClient.get(
      `/db/security/permission-management/types/type/${targetType}`
    );
    return response.data;
  }

  static async deleteTypePermission(permissionId: string): Promise<void> {
    await apiClient.delete(`/db/security/permission-management/types/${permissionId}`);
  }

  static async grantFullAccess(roleId: string, targetType: string): Promise<TypePermission> {
    const response = await apiClient.post(
      `/db/security/permission-management/types/grant-full-access/${roleId}/${targetType}`
    );
    return response.data;
  }

  static async grantReadOnly(roleId: string, targetType: string): Promise<TypePermission> {
    const response = await apiClient.post(
      `/db/security/permission-management/types/grant-read-only/${roleId}/${targetType}`
    );
    return response.data;
  }

  // ===== Utility =====

  static async getAllActions(): Promise<{ actions: string[] }> {
    const response = await apiClient.get('/db/security/permission-management/all-actions');
    return response.data;
  }

  static async getAllPaths(): Promise<{ paths: string[] }> {
    const response = await apiClient.get('/db/security/permission-management/all-paths');
    return response.data;
  }

  static async getAllTypes(): Promise<{ types: string[] }> {
    const response = await apiClient.get('/db/security/permission-management/all-types');
    return response.data;
  }

  static async getRolePermissionsSummary(roleId: string): Promise<RolePermissionsSummary> {
    const response = await apiClient.get(
      `/db/security/permission-management/role/${roleId}/summary`
    );
    return response.data;
  }
}

// ==================== EXPORT DEFAULT ====================

export default {
  Role: RoleAPI,
  UserRole: UserRoleAPI,
  Permission: PermissionAPI,
  PermissionManagement: PermissionManagementAPI,
};
