import type { ApiUser } from '../../auth/api/userApi.ts';

// Updated interface to match API response
export interface UserData {
    id: string;
    username: string;
    active: boolean;
    created_date: Date | null;
    last_modified_date: Date | null;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    change_password_on_first_logon?: boolean;
    object_type?: number;
    access_failed_count?: number;
    lockout_end?: Date | null;
}

export interface UserFormData {
    username: string;
    password: string;
    confirmPassword: string;
    active: boolean;
    change_password_on_first_logon: boolean;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    object_type?: number;
}

export interface SnackbarState {
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info' | 'warning';
}

export const createEmptyUserForm = (): UserFormData => ({
    username: '',
    password: '',
    confirmPassword: '',
    active: true,
    change_password_on_first_logon: false,
    omid: undefined,
    ouid: '',
    sync_status: undefined,
    version: '',
    object_type: undefined
});

// Convert API user to component user format
export const convertApiUserToUserData = (apiUser: ApiUser): UserData => ({
    id: apiUser.oid,
    username: apiUser.username || '',
    active: apiUser.active || false,
    created_date: apiUser.created_date ? new Date(apiUser.created_date) : null,
    last_modified_date: apiUser.last_modified_date ? new Date(apiUser.last_modified_date) : null,
    omid: apiUser.omid,
    ouid: apiUser.ouid,
    sync_status: apiUser.sync_status,
    version: apiUser.version,
    change_password_on_first_logon: apiUser.change_password_on_first_logon,
    object_type: apiUser.object_type,
    access_failed_count: apiUser.access_failed_count,
    lockout_end: apiUser.lockout_end ? new Date(apiUser.lockout_end) : null
});
