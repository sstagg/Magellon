const ACCESS_TOKEN_KEY = 'access_token';

export function getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAuthStorage(): void {
    for (const key of [ACCESS_TOKEN_KEY, 'currentUser', 'currentUserId', 'user']) {
        localStorage.removeItem(key);
    }
}

