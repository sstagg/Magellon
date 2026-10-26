import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAuth } from '../../../features/auth/model/AuthContext.tsx';
import type { UserCapabilities } from '../../../features/auth/api/userApi.ts';

interface RequireCapabilityProps {
    capability: keyof UserCapabilities;
    children: ReactNode;
}

/**
 * Keeps users out of pages whose actions the backend would refuse anyway
 * (typed URL, old bookmark) — the menu already hides the link. Not a
 * security boundary: every endpoint still checks permissions itself.
 */
export const RequireCapability = ({ capability, children }: RequireCapabilityProps) => {
    const { capabilities, capabilitiesLoaded } = useAuth();

    if (!capabilitiesLoaded) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 240 }}>
                <CircularProgress />
            </Box>
        );
    }
    if (!capabilities[capability]) {
        return <Navigate to="/en/panel/images" replace />;
    }
    return <>{children}</>;
};

export default RequireCapability;
