import SwaggerUI from "swagger-ui-react"
import "swagger-ui-react/swagger-ui.css"
import {settings} from "../../shared/config/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_API_URL ;

export const ApiView = () => {
    // console.log("ApisView");
    return (
        <SwaggerUI url={`${BASE_URL}/openapi.json`} />
    );
};
