import SwaggerUI from "swagger-ui-react"
import "swagger-ui-react/swagger-ui.css"
export const ApiView = () => {
    console.log("ApisView");
    return (
        <SwaggerUI url="http://127.0.0.1:8000/openapi.json" />
    );
};
