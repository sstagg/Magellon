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
    message: string;
    user_id: string;
    username: string;
    change_password_required: boolean;
}

export interface UserStats {
    total_users: number;
    include_inactive: boolean;
}

class UserApiService {
    private baseUrl = 'http://localhost:8000/db/users';

    private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
        }

        return response.json();
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
        return this.request<ApiUser[]>(endpoint);
    }

    // Get user by ID
    async getUserById(userId: string): Promise<ApiUser> {
        return this.request<ApiUser>(`/${userId}`);
    }

    // Get user by username
    async getUserByUsername(username: string): Promise<ApiUser> {
        return this.request<ApiUser>(`/username/${username}`);
    }

    // Create new user
    async createUser(userData: CreateUserRequest): Promise<ApiUser> {
        return this.request<ApiUser>('/', {
            method: 'POST',
            body: JSON.stringify(userData),
        });
    }

    // Update user
    async updateUser(userData: UpdateUserRequest): Promise<ApiUser> {
        return this.request<ApiUser>('/', {
            method: 'PUT',
            body: JSON.stringify(userData),
        });
    }

    // Delete user
    async deleteUser(userId: string, hardDelete: boolean = false): Promise<{ message: string }> {
        const searchParams = new URLSearchParams();
        if (hardDelete) searchParams.set('hard_delete', 'true');

        return this.request<{ message: string }>(`/${userId}?${searchParams.toString()}`, {
            method: 'DELETE',
        });
    }

    // Authenticate user
    async authenticate(credentials: AuthenticationRequest): Promise<AuthenticationResponse> {
        const searchParams = new URLSearchParams();
        searchParams.set('username', credentials.username);
        searchParams.set('password', credentials.password);

        return this.request<AuthenticationResponse>(`/authenticate?${searchParams.toString()}`, {
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

    // Change password
    async changePassword(userId: string, currentPassword: string, newPassword: string): Promise<{ message: string }> {
        const searchParams = new URLSearchParams();
        searchParams.set('current_password', currentPassword);
        searchParams.set('new_password', newPassword);

        return this.request<{ message: string }>(`/${userId}/change-password?${searchParams.toString()}`, {
            method: 'POST',
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