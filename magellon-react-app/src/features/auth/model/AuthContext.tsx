// panel/pages/UserManagement/AuthContext.tsx
import type { ReactNode } from 'react';
import React, { createContext, useContext, useState, useEffect } from 'react';
import type { AuthenticationResponse, UserCapabilities } from '../api/userApi.ts';
import { userApiService } from '../api/userApi.ts';
import { clearAuthStorage, setAccessToken } from '../../../shared/auth/tokenStore';
import { useSocket } from '../../../shared/lib/useSocket.ts';

export interface User {
    id: string;
    username: string;
    active: boolean;
    change_password_required: boolean;
}

const NO_CAPABILITIES: UserCapabilities = { admin: false, import_sessions: false, view_all_sessions: false };

interface AuthContextType {
    user: User | null;
    loading: boolean;
    /** What the UI should offer this user (from /auth/me). Hides options the
     *  backend would refuse; it is not itself a security boundary. */
    capabilities: UserCapabilities;
    capabilitiesLoaded: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    isAuthenticated: boolean;
    checkAuth: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Mounted only while someone is logged in, so the shared socket connects
 * with their token and joins their personal room. The server pushes
 * ``permissions_changed`` the moment an admin changes their roles; a
 * (re)connect also re-reads, covering changes made while offline.
 */
const PermissionsListener = ({ onChange }: { onChange: () => void }) => {
    const { on, connected } = useSocket();
    useEffect(() => on('permissions_changed', onChange), [on, onChange]);
    useEffect(() => { if (connected) onChange(); }, [connected, onChange]);
    return null;
};

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [capabilities, setCapabilities] = useState<UserCapabilities>(NO_CAPABILITIES);
    const [capabilitiesLoaded, setCapabilitiesLoaded] = useState(false);

    // Always asked from the server (never cached), so a role change shows
    // up on the next page load without logging out.
    const loadCapabilities = React.useCallback(async () => {
        try {
            const me = await userApiService.getCurrentUser();
            setCapabilities(me.capabilities ?? NO_CAPABILITIES);
        } catch (error) {
            console.error('Failed to load user capabilities:', error);
            setCapabilities(NO_CAPABILITIES);
        } finally {
            setCapabilitiesLoaded(true);
        }
    }, []);

    // Check if user is already logged in on app start
    useEffect(() => {
        checkAuth();
    }, []);

    useEffect(() => {
        if (user) {
            loadCapabilities();
        } else {
            setCapabilities(NO_CAPABILITIES);
            setCapabilitiesLoaded(false);
        }
    }, [user?.id]);

    const checkAuth = () => {
        const savedUser = localStorage.getItem('currentUser');
        const savedUserId = localStorage.getItem('currentUserId');

        if (savedUser && savedUserId) {
            try {
                const parsedUser = JSON.parse(savedUser);
                setUser(parsedUser);
            } catch (error) {
                console.error('Failed to parse saved user data:', error);
                localStorage.removeItem('currentUser');
                localStorage.removeItem('currentUserId');
            }
        }
        setLoading(false);
    };

    // Doesn't touch `loading`: that flag means "checking for an existing
    // session at app start", and the route tree swaps every page for a
    // spinner while it is set — which unmounted the login page mid-attempt,
    // so a failed login came back as a fresh form with its error lost.
    // The login page shows its own progress.
    const login = async (username: string, password: string): Promise<void> => {
        const authResponse: AuthenticationResponse = await userApiService.authenticate({
            username,
            password
        });

        // Store JWT token
        setAccessToken(authResponse.access_token);

        const userData: User = {
            id: authResponse.user_id,
            username: authResponse.username,
            active: true,
            change_password_required: authResponse.change_password_required || false
        };

        setUser(userData);

        // Save user info to localStorage for persistence
        localStorage.setItem('currentUser', JSON.stringify(userData));
        localStorage.setItem('currentUserId', authResponse.user_id);
    };

    const logout = async () => {
        try {
            // Call logout endpoint to invalidate token on server
            await userApiService.logout();
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear local state and storage regardless of API call result
            setUser(null);
            clearAuthStorage();
        }
    };

    const value: AuthContextType = {
        user,
        loading,
        capabilities,
        capabilitiesLoaded,
        login,
        logout,
        isAuthenticated: !!user,
        checkAuth
    };

    return (
        <AuthContext.Provider value={value}>
            {user && <PermissionsListener onChange={loadCapabilities} />}
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
