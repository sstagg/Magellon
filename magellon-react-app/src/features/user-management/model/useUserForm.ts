import { useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { UserData, UserFormData } from './types.ts';
import { createEmptyUserForm } from './types.ts';

export interface UserFormState {
    formData: UserFormData;
    setFormData: Dispatch<SetStateAction<UserFormData>>;
    showPassword: boolean;
    setShowPassword: Dispatch<SetStateAction<boolean>>;
    showConfirmPassword: boolean;
    setShowConfirmPassword: Dispatch<SetStateAction<boolean>>;
    resetForm: () => void;
    populateForm: (user: UserData) => void;
}

export const useUserForm = (): UserFormState => {
    // Form state
    const [formData, setFormData] = useState<UserFormData>(createEmptyUserForm());

    // UI state
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);

    const resetForm = () => {
        setFormData(createEmptyUserForm());
    };

    const populateForm = (user: UserData) => {
        setFormData({
            username: user.username,
            password: '',
            confirmPassword: '',
            active: user.active,
            change_password_on_first_logon: user.change_password_on_first_logon || false,
            omid: user.omid,
            ouid: user.ouid || '',
            sync_status: user.sync_status,
            version: user.version || '',
            object_type: user.object_type
        });
    };

    return {
        formData,
        setFormData,
        showPassword,
        setShowPassword,
        showConfirmPassword,
        setShowConfirmPassword,
        resetForm,
        populateForm
    };
};
