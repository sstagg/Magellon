import React from 'react';
import { Alert, AlertTitle, Box, Collapse, Typography } from '@mui/material';

interface ValidationErrorsAlertProps {
    open: boolean;
    errors: string[];
}

/** Collapsible "fix before running" list of validation errors. */
export const ValidationErrorsAlert: React.FC<ValidationErrorsAlertProps> = ({ open, errors }) => (
    <Collapse in={open}>
        <Box sx={{ px: 1.5, pt: 1 }}>
            <Alert severity="warning" sx={{ py: 0.25, '& .MuiAlert-message': { fontSize: '0.7rem' } }}>
                <AlertTitle sx={{ fontSize: '0.75rem', mb: 0.25 }}>Fix before running</AlertTitle>
                {errors.map((err, i) => (
                    <Typography
                        key={i}
                        variant="caption"
                        sx={{
                            display: "block",
                            lineHeight: 1.5,
                            fontSize: '0.7rem'
                        }}>• {err}</Typography>
                ))}
            </Alert>
        </Box>
    </Collapse>
);
