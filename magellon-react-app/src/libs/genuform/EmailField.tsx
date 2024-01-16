import React from 'react';
import { TextField } from '@mui/material';
import { UseFormRegisterReturn } from 'react-hook-form';

interface EmailFieldProps {
    register: UseFormRegisterReturn;
    errors: any;
}

const EmailField: React.FC<EmailFieldProps> = ({ register, errors }) => (
    <TextField
        label="Email"
        {...register('email', {
            required: 'Email is required',
            pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Invalid email address format',
            },
        })}
        error={!!errors.email}
        helperText={errors.email ? errors.email.message : ''}
    />
);

export default EmailField;
