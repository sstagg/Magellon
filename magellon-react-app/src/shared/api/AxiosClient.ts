import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios";

export function createAxiosClient(baseUrl: string): AxiosInstance {
    const AxiosClient = axios.create({
        baseURL: baseUrl,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    // Request interceptor - Add JWT token to all requests
    AxiosClient.interceptors.request.use(
        (config: InternalAxiosRequestConfig) => {
            // Try to get token from localStorage
            const token = localStorage.getItem('access_token');

            // Fallback to old user object if no token found
            if (!token && localStorage.getItem("user")) {
                try {
                    const userToken = JSON.parse(localStorage.getItem("user")!).token;
                    if (userToken && config.headers) {
                        config.headers.Authorization = `Bearer ${userToken}`;
                    }
                } catch (e) {
                    console.error('Failed to parse user token:', e);
                }
            } else if (token && config.headers) {
                config.headers.Authorization = `Bearer ${token}`;
            }

            return config;
        },
        (error) => {
            return Promise.reject(error);
        }
    );

    // Response interceptor - Handle 401 errors and token refresh
    AxiosClient.interceptors.response.use(
        (response) => response,
        async (error: AxiosError) => {
            const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

            // If 401 error and we haven't retried yet
            if (error.response?.status === 401 && !originalRequest._retry) {
                originalRequest._retry = true;

                const token = localStorage.getItem('access_token');

                if (token) {
                    try {
                        // Try to refresh token
                        const response = await axios.post(
                            `${baseUrl}/auth/refresh`,
                            {},
                            {
                                headers: { Authorization: `Bearer ${token}` }
                            }
                        );

                        const newToken = response.data.access_token;

                        // Store new token
                        localStorage.setItem('access_token', newToken);

                        // Retry original request with new token
                        if (originalRequest.headers) {
                            originalRequest.headers.Authorization = `Bearer ${newToken}`;
                        }

                        return AxiosClient(originalRequest);

                    } catch (refreshError) {
                        // Refresh failed - logout user
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('currentUser');
                        localStorage.removeItem('currentUserId');
                        localStorage.removeItem('user'); // Remove old user object too

                        // Redirect to login if not already there
                        if (!window.location.pathname.includes('/login')) {
                            window.location.href = '/en/account/login';
                        }

                        return Promise.reject(refreshError);
                    }
                } else {
                    // No token - redirect to login
                    localStorage.removeItem('currentUser');
                    localStorage.removeItem('currentUserId');
                    localStorage.removeItem('user'); // Remove old user object too

                    if (!window.location.pathname.includes('/login')) {
                        window.location.href = '/en/account/login';
                    }
                }
            }

            // Handle 403 Forbidden errors
            if (error.response?.status === 403) {
                console.error('Permission denied:', error.response.data);
                // You can dispatch a global error event here if needed
            }

            return Promise.reject(error);
        }
    );

    return AxiosClient;
}

// Create a private variable to hold the AxiosClient instance
let instance: AxiosInstance | null = null;

// Create a function to create or retrieve the AxiosClient instance
function getAxiosClient(baseUrl: string): AxiosInstance {
    if (!instance) {
        // If the instance doesn't exist, create it
        instance = createAxiosClient(baseUrl);
        // Add request interceptors or other configurations here
    }
    return instance;
}

export default getAxiosClient;