import axios, { AxiosInstance } from "axios";
export function createAxiosClient(baseUrl: string): AxiosInstance {
    const AxiosClient = axios.create({
        baseURL: baseUrl,
    });
    AxiosClient.interceptors.request.use((req) => {
        if (localStorage.getItem("user")) {
            const token = JSON.parse(localStorage.getItem("user")).token;
            req.headers.Authorization = `Bearer ${token}`;
        }
        return req;
    });
    return AxiosClient;
}

// Create a private variable to hold the AxiosClient instance
let instance: AxiosInstance | null = null;

// Create a function to create or retrieve the AxiosClient instance
function getAxiosClient(baseUrl: string): AxiosInstance {
    if (!instance) {
        // If the instance doesn't exist, create it
        instance = createAxiosClient(baseUrl)
        // Add request interceptors or other configurations here
    }
    return instance;
}

export default getAxiosClient;