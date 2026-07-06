
import configData from "./configs.json";

// Runtime overrides: /config.js (loaded synchronously in index.html
// before the bundle) sets window.__MAGELLON_CONFIG__. In the Docker
// image the nginx entrypoint generates that file from env vars at
// container start, so one image can point at any backend without a
// rebuild. Dev servers fall back to configs.json defaults.
declare global {
    interface Window {
        __MAGELLON_CONFIG__?: Partial<typeof configData>;
    }
}

const runtimeConfig =
    typeof window !== "undefined" ? window.__MAGELLON_CONFIG__ ?? {} : {};

export const settings = {
    // VERSION: process.env.VERSION,
    drawerWidth: 260,
    twitterColor: '#1DA1F2',
    facebookColor: '#3b5998',
    linkedInColor: '#0e76a8',

    // SERVER_API_URL: "http://api.phaiton.com/",
    AUTHORITIES: {
        ADMIN: 'ROLE_ADMIN',
        USER: 'ROLE_USER'
    },
    messages: {
        DATA_ERROR_ALERT: 'Internal Error'
    },
    APP_DATE_FORMAT: 'DD/MM/YY HH:mm',
    APP_TIMESTAMP_FORMAT: 'DD/MM/YY HH:mm:ss',
    APP_LOCAL_DATE_FORMAT: 'DD/MM/YYYY',
    APP_LOCAL_DATETIME_FORMAT: 'YYYY-MM-DDTHH:mm',
    APP_LOCAL_DATETIME_FORMAT_Z: 'YYYY-MM-DDTHH:mm Z',
    APP_WHOLE_NUMBER_FORMAT: '0,0',
    APP_TWO_DIGITS_AFTER_POINT_NUMBER_FORMAT: '0,0.[00]',
    apiBaseUrl : 'https://jsonplaceholder.typicode.com/',
// Define the API endpoints
    api_endpoints : {
        blogs: 'posts',
        searchBlogs: 'admin/_search/blogs',
    },
    ConfigData: { ...configData, ...runtimeConfig }
};

