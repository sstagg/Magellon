import React, { useEffect, useState } from 'react';
import {
    Box,
    CircularProgress,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TablePagination,
    TableRow,
    TableSortLabel,
    Typography,
} from '@mui/material';
import type ImageInfoDto from '../../../entities/image/types.ts';
import { useImagesPage } from '../api/usePagedImagesHook.ts';
import type { ImageSort } from '../api/imagesApiReactQuery.tsx';
import { countActiveFilters } from '../lib/imageFilter.ts';
import { openImageWithAncestors } from '../lib/imagePath.ts';
import { useImageViewerStore } from '../model/imageViewerStore.ts';

const COLUMNS: Array<{ sort: Exclude<ImageSort, 'related'>; label: string; show: (image: ImageInfoDto) => string }> = [
    { sort: 'name', label: 'Name', show: (image) => image.name ?? '' },
    { sort: 'mag', label: 'Mag', show: (image) => (image.mag != null ? String(image.mag) : '—') },
    { sort: 'defocus', label: 'Defocus (μm)', show: (image) => image.defocus?.toFixed(2) ?? '—' },
    { sort: 'resolution', label: 'Resolution (Å)', show: (image) => image.resolution?.toFixed(2) ?? '—' },
    { sort: 'pixelSize', label: 'Pixel (Å)', show: (image) => image.pixelSize?.toFixed(3) ?? '—' },
    { sort: 'children', label: 'Children', show: (image) => String(image.children_count ?? 0) },
];

/**
 * Every image of a session in a table. The server filters, sorts and pages:
 * related images first until a column is sorted, empty values last.
 */
export const ImageTable: React.FC<{
    sessionName: string;
    onImageClick: (image: ImageInfoDto, column: number) => void;
}> = ({ sessionName, onImageClick }) => {
    const { currentImage, imageColumns, imageFilter: filter } = useImageViewerStore();
    const [sort, setSort] = useState<{ field: Exclude<ImageSort, 'related'>; descending: boolean } | null>(null);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(50);

    useEffect(() => setPage(0), [filter]);

    const { data, isLoading, isFetching } = useImagesPage(sessionName, page + 1, rowsPerPage, {
        allLevels: true,
        filter,
        sort: sort?.field ?? 'related',
        order: sort?.descending ? 'desc' : 'asc',
    });
    const rows = data?.result ?? [];
    const total = data?.total_count ?? 0;

    const toggleSort = (field: Exclude<ImageSort, 'related'>) => {
        setSort((current) => ({ field, descending: current?.field === field && !current.descending }));
        setPage(0);
    };

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }} data-testid="image-table">
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, py: 1, flexShrink: 0 }}>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    {total} images{countActiveFilters(filter) > 0 && ' matching the filter'}{isFetching && ' (loading...)'}
                </Typography>
            </Box>
            <TableContainer sx={{ flex: 1, minHeight: 0 }}>
                <Table stickyHeader size="small">
                    <TableHead>
                        <TableRow>
                            {COLUMNS.map(({ sort: field, label }) => (
                                <TableCell key={field} sortDirection={sort?.field === field ? (sort.descending ? 'desc' : 'asc') : false} sx={{ whiteSpace: 'nowrap' }}>
                                    <TableSortLabel
                                        active={sort?.field === field}
                                        direction={sort?.field === field && sort.descending ? 'desc' : 'asc'}
                                        onClick={() => toggleSort(field)}
                                    >
                                        {label}
                                    </TableSortLabel>
                                </TableCell>
                            ))}
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rows.map((image) => (
                            <TableRow
                                key={image.oid}
                                hover
                                selected={currentImage?.oid === image.oid}
                                onClick={() => openImageWithAncestors(image, imageColumns.length, onImageClick)}
                                sx={{ cursor: 'pointer' }}
                            >
                                {COLUMNS.map(({ sort: field, show }) => (
                                    <TableCell key={field} sx={{ whiteSpace: 'nowrap' }}>{show(image)}</TableCell>
                                ))}
                            </TableRow>
                        ))}
                        {rows.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={COLUMNS.length} align="center" sx={{ color: 'text.secondary', py: 4 }}>
                                    {countActiveFilters(filter) > 0 ? 'No images match the current filters' : 'No images available'}
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
            <TablePagination
                component="div"
                count={total}
                page={total === 0 ? 0 : Math.min(page, Math.ceil(total / rowsPerPage) - 1)}
                onPageChange={(_, next) => setPage(next)}
                rowsPerPage={rowsPerPage}
                rowsPerPageOptions={[25, 50, 100]}
                onRowsPerPageChange={(event) => {
                    setRowsPerPage(Number(event.target.value));
                    setPage(0);
                }}
                // Left-aligned and wrapping: the panel can be narrow, and the atlas button sits bottom right.
                sx={{
                    flexShrink: 0,
                    '& .MuiTablePagination-toolbar': { flexWrap: 'wrap', justifyContent: 'flex-start', pl: 2, pr: 9 },
                    '& .MuiTablePagination-spacer': { display: 'none' },
                }}
            />
        </Box>
    );
};

export default ImageTable;
