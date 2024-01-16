import React from "react";
import {LinearProgress} from "@mui/material";
import Button from '@mui/material/Button';
import errorImage from "../assets/images/error1.jpg";
import emptyImage from "../assets/images/empty-state1.jpg";

interface EmptyStateProps {
    isLoading: boolean;
    isError: boolean;
    data?: any; // Update with the actual data type if needed
    retryHandler?: (event) => void;
    loadingMessage?: string;
    errorMessage?: string;
    noDataMessage?: string;
    retryButtonText?: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({
                                                   isLoading,
                                                   isError,
                                                   data,
                                                   retryHandler,
                                                   loadingMessage = "Loading...",
                                                   errorMessage = "Error loading the content.",
                                                   noDataMessage = "No data found.",
                                                   retryButtonText = "Retry",
                                               }) => {

    if (isLoading) {
        return (
            <div>
                <LinearProgress color="secondary" />
                <h3>{loadingMessage}</h3>
            </div>
        );
    } else if (isError) {
        return (
            <div>
                <h3>{errorMessage}</h3>
                <img src={errorImage} alt="Error loading" style={{ maxWidth: "300px" }} />
                {retryHandler && (
                    <Button type="button" onClick={retryHandler}>
                        {retryButtonText}
                    </Button>
                )}
            </div>
        );
    } else if (!data) {
        return (
            <div>
                <h3>{noDataMessage}</h3>
                <img src={emptyImage} alt="No data found" style={{ maxWidth: "300px" }} />
            </div>
        );
    }

};
export default EmptyState;