
import configData from "../config/configs.json";
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
    ConfigData: configData
};

