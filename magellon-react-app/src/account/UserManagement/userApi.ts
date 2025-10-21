// services/userApi.ts

export interface ApiUser {
    oid: string;
    username?: string;
    active?: boolean;
    created_date?: string;
    last_modified_date?: string;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    change_password_on_first_logon?: boolean;
    object_type?: number;
    access_failed_count?: number;
    lockout_end?: string;
}

export interface CreateUserRequest {
    username: string;
    password: string;
    active?: boolean;
    change_password_on_first_logon?: boolean;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    object_type?: number;
}

export interface UpdateUserRequest {
    oid: string;
    username?: string;
    password?: string;
    active?: boolean;
    change_password_on_first_logon?: boolean;
    omid?: number;
    ouid?: string;
    sync_status?: number;
    version?: string;
    object_type?: number;
    access_failed_count?: number;
    lockout_end?: string;
}

export interface AuthenticationRequest {
    username: string;
    password: string;
}

export interface AuthenticationResponse {
    access_token: string;
    token_type: string;
    user_id: string;
    username: string;
    expires_in: number;
    change_password_required?: boolean;
}

export interface UserMeResponse {
    user_id: string;
    username: string;
    email: string | null;
    active: boolean;
}

export interface UserStats {
    total_users: number;
    include_inactive: boolean;
}

class UserApiService {
    private baseUrl = 'http://localhost:8000/db/security/users';
    private authBaseUrl = 'http://localhost:8000/auth';

    private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;

        // Add Authorization header if token exists
        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
        }

        return response.json();
    }

    private async authRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${this.authBaseUrl}${endpoint}`;

        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
        }

        return response.json();
    }

    // Transform API response from uppercase to lowercase field names
    private transformUser(apiUser: any): ApiUser {
        return {
            oid: apiUser.oid,
            username: apiUser.USERNAME || apiUser.username,
            active: apiUser.ACTIVE !== undefined ? apiUser.ACTIVE : apiUser.active,
            created_date: apiUser.created_date,
            last_modified_date: apiUser.last_modified_date,
            omid: apiUser.omid,
            ouid: apiUser.ouid,
            sync_status: apiUser.sync_status,
            version: apiUser.version,
            change_password_on_first_logon: apiUser.ChangePasswordOnFirstLogon || apiUser.change_password_on_first_logon,
            object_type: apiUser.ObjectType || apiUser.object_type,
            access_failed_count: apiUser.AccessFailedCount || apiUser.access_failed_count,
            lockout_end: apiUser.LockoutEnd || apiUser.lockout_end,
        };
    }

    // Get all users with pagination and filters
    async getUsers(params: {
        skip?: number;
        limit?: number;
        username?: string;
        include_inactive?: boolean;
    } = {}): Promise<ApiUser[]> {
        const searchParams = new URLSearchParams();

        if (params.skip !== undefined) searchParams.set('skip', params.skip.toString());
        if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
        if (params.username) searchParams.set('username', params.username);
        if (params.include_inactive !== undefined) searchParams.set('include_inactive', params.include_inactive.toString());

        const endpoint = `/?${searchParams.toString()}`;
        const users = await this.request<any[]>(endpoint);
        return users.map(user => this.transformUser(user));
    }

    // Get user by ID
    async getUserById(userId: string): Promise<ApiUser> {
        const user = await this.request<any>(`/${userId}`);
        return this.transformUser(user);
    }

    // Get user by username
    async getUserByUsername(username: string): Promise<ApiUser> {
        const user = await this.request<any>(`/username/${username}`);
        return this.transformUser(user);
    }

    // Create new user
    async createUser(userData: CreateUserRequest): Promise<ApiUser> {
        const user = await this.request<any>('/', {
            method: 'POST',
            body: JSON.stringify(userData),
        });
        return this.transformUser(user);
    }

    // Update user
    async updateUser(userData: UpdateUserRequest): Promise<ApiUser> {
        const user = await this.request<any>('/', {
            method: 'PUT',
            body: JSON.stringify(userData),
        });
        return this.transformUser(user);
    }

    // Delete user
    async deleteUser(userId: string, hardDelete: boolean = false): Promise<{ message: string }> {
        const searchParams = new URLSearchParams();
        if (hardDelete) searchParams.set('hard_delete', 'true');

        return this.request<{ message: string }>(`/${userId}?${searchParams.toString()}`, {
            method: 'DELETE',
        });
    }

    // Authenticate user - NEW JWT endpoint
    async authenticate(credentials: AuthenticationRequest): Promise<AuthenticationResponse> {
        return this.authRequest<AuthenticationResponse>('/login', {
            method: 'POST',
            body: JSON.stringify(credentials),
        });
    }

    // Get current user info
    async getCurrentUser(): Promise<UserMeResponse> {
        return this.authRequest<UserMeResponse>('/me', {
            method: 'GET',
        });
    }

    // Refresh token
    async refreshToken(): Promise<AuthenticationResponse> {
        return this.authRequest<AuthenticationResponse>('/refresh', {
            method: 'POST',
        });
    }

    // Logout
    async logout(): Promise<{ message: string }> {
        return this.authRequest<{ message: string }>('/logout', {
            method: 'POST',
        });
    }

    // Activate user
    async activateUser(userId: string): Promise<{ message: string }> {
        return this.request<{ message: string }>(`/${userId}/activate`, {
            method: 'POST',
        });
    }

    // Deactivate user
    async deactivateUser(userId: string): Promise<{ message: string }> {
        return this.request<{ message: string }>(`/${userId}/deactivate`, {
            method: 'POST',
        });
    }

    // Unlock user
    async unlockUser(userId: string): Promise<{ message: string }> {
        return this.request<{ message: string }>(`/${userId}/unlock`, {
            method: 'POST',
        });
    }

    // Change password (user changing their own password - requires current password)
    async changePassword(userId: string, currentPassword: string, newPassword: string): Promise<{ message: string }> {
        const searchParams = new URLSearchParams();
        searchParams.set('current_password', currentPassword);
        searchParams.set('new_password', newPassword);

        return this.request<{ message: string }>(`/${userId}/change-password?${searchParams.toString()}`, {
            method: 'POST',
        });
    }

    // Admin reset password (admin resetting user password - no current password required)
    async adminResetPassword(
        userId: string,
        newPassword: string,
        requireChangeOnLogin: boolean = false
    ): Promise<{ message: string }> {
        return this.request<{ message: string }>(`/${userId}/admin-reset-password`, {
            method: 'POST',
            body: JSON.stringify({
                new_password: newPassword,
                require_change_on_login: requireChangeOnLogin,
            }),
        });
    }

    // Get user statistics
    async getUserStats(includeInactive: boolean = false): Promise<UserStats> {
        const searchParams = new URLSearchParams();
        searchParams.set('include_inactive', includeInactive.toString());

        return this.request<UserStats>(`/stats/count?${searchParams.toString()}`);
    }
}

export const userApiService = new UserApiService();