import {
    Button,
    FormControl,
    Grid,
    InputAdornment,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    TextField
} from '@mui/material';
import { Refresh, Search } from '@mui/icons-material';

interface UserFiltersProps {
    searchTerm: string;
    onSearchTermChange: (searchTerm: string) => void;
    statusFilter: string;
    onStatusFilterChange: (statusFilter: string) => void;
    loading: boolean;
    onRefresh: () => void;
}

export default function UserFilters({
    searchTerm,
    onSearchTermChange,
    statusFilter,
    onStatusFilterChange,
    loading,
    onRefresh
}: UserFiltersProps) {
    return (
        <Paper sx={{ p: 2, mb: 3 }}>
            <Grid container spacing={2} sx={{
                alignItems: "center"
            }}>
                <Grid
                    size={{
                        xs: 12,
                        md: 6
                    }}>
                    <TextField
                        fullWidth
                        placeholder="Search users..."
                        value={searchTerm}
                        onChange={(e) => onSearchTermChange(e.target.value)}
                        slotProps={{
                            input: {
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <Search />
                                    </InputAdornment>
                                )
                            }
                        }}
                    />
                </Grid>
                <Grid
                    size={{
                        xs: 12,
                        sm: 6,
                        md: 3
                    }}>
                    <FormControl fullWidth>
                        <InputLabel>Status</InputLabel>
                        <Select
                            value={statusFilter}
                            onChange={(e) => onStatusFilterChange(e.target.value)}
                            label="Status"
                        >
                            <MenuItem value="all">All Status</MenuItem>
                            <MenuItem value="active">Active</MenuItem>
                            <MenuItem value="inactive">Inactive</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                <Grid
                    size={{
                        xs: 12,
                        md: 3
                    }}>
                    <Button
                        startIcon={<Refresh />}
                        onClick={onRefresh}
                        disabled={loading}
                        fullWidth
                    >
                        {loading ? 'Loading...' : 'Refresh'}
                    </Button>
                </Grid>
            </Grid>
        </Paper>
    );
}
