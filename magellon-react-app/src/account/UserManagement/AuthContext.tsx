// panel/pages/UserManagement/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { userApiService, AuthenticationResponse } from './userApi.ts';

interface User {
    id: string;
    username: string;
    active: boolean;
    change_password_required: boolean;
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    isAuthenticated: boolean;
    checkAuth: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    // Check if user is already logged in on app start
    useEffect(() => {
        checkAuth();
    }, []);

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

    const login = async (username: string, password: string): Promise<void> => {
        setLoading(true);
        try {
            const authResponse: AuthenticationResponse = await userApiService.authenticate({
                username,
                password
            });

            // Store JWT token
            localStorage.setItem('access_token', authResponse.access_token);

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

        } catch (error) {
            throw error;
        } finally {
            setLoading(false);
        }
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
            localStorage.removeItem('access_token');
            localStorage.removeItem('currentUser');
            localStorage.removeItem('currentUserId');
        }
    };

    const value: AuthContextType = {
        user,
        loading,
        login,
        logout,
        isAuthenticated: !!user,
        checkAuth
    };

    return (
        <AuthContext.Provider value={value}>
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