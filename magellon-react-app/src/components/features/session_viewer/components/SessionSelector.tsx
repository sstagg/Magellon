import React from 'react';
import {
    Paper,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    SelectChangeEvent
} from '@mui/material';
import { SessionDto } from '../ImageInfoDto';

interface SessionSelectorProps {
    selectedSession: SessionDto | null;
    sessions: SessionDto[];
    onSessionChange: (event: SelectChangeEvent) => void;
}

export const SessionSelector: React.FC<SessionSelectorProps> = ({
    selectedSession,
    sessions,
    onSessionChange
}) => {
    return (
        <Paper elevation={0} variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
            <FormControl fullWidth size="small" variant="outlined">
                <InputLabel id="session-select-label">Session</InputLabel>
                <Select
                    labelId="session-select-label"
                    id="session-select"
                    value={selectedSession?.name || ""}
                    label="Session"
                    onChange={onSessionChange}
                >
                    <MenuItem value="">
                        <em>None</em>
                    </MenuItem>
                    {sessions?.map((session) => (
                        <MenuItem key={session.Oid} value={session.name}>
                            {session.name}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>
        </Paper>
    );
};
