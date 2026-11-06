import React, { useMemo, useState } from 'react';
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
import { useAllSessionImages } from '../api/usePagedImagesHook.ts';
import { makeImageMatcher } from '../lib/imageFilter.ts';
import { openImagePath } from '../lib/imagePath.ts';
import { useImageViewerStore } from '../model/imageViewerStore.ts';

type SortField = 'name' | 'mag' | 'defocus' | 'resolution' | 'pixelSize' | 'children_count';

const COLUMNS: Array<{ field: SortField; label: string; show: (image: ImageInfoDto) => string }> = [
    { field: 'name', label: 'Name', show: (image) => image.name ?? '' },
    { field: 'mag', label: 'Mag', show: (image) => (image.mag != null ? String(image.mag) : '—') },
    { field: 'defocus', label: 'Defocus (μm)', show: (image) => image.defocus?.toFixed(2) ?? '—' },
    { field: 'resolution', label: 'Resolution (Å)', show: (image) => image.resolution?.toFixed(2) ?? '—' },
    { field: 'pixelSize', label: 'Pixel (Å)', show: (image) => image.pixelSize?.toFixed(3) ?? '—' },
    { field: 'children_count', label: 'Children', show: (image) => String(image.children_count ?? 0) },
];

/** Empty values last in either direction. */
const compare = (a: ImageInfoDto, b: ImageInfoDto, field: SortField, descending: boolean): number => {
    const x = a[field];
    const y = b[field];
    if (x == null || y == null) return Number(x == null) - Number(y == null);
    const order = x < y ? -1 : x > y ? 1 : 0;
    return descending ? -order : order;
};

/** Every image of a session in a table; related images come first until a column is sorted. */
export const ImageTable: React.FC<{
    sessionName: string;
    onImageClick: (image: ImageInfoDto, column: number) => void;
}> = ({ sessionName, onImageClick }) => {
    const { currentImage, imageColumns, imageFilter: filter } = useImageViewerStore();
    const { images, isLoading, isLoadingMore } = useAllSessionImages(sessionName);
    const [sort, setSort] = useState<{ field: SortField; descending: boolean } | null>(null);
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(50);

    const rows = useMemo(() => {
        const matches = makeImageMatcher(filter);
        const filtered = matches ? images.filter(matches) : [...images];
        return sort ? filtered.sort((a, b) => compare(a, b, sort.field, sort.descending)) : filtered;
    }, [images, filter, sort]);

    const toggleSort = (field: SortField) => {
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
                    {rows.length} of {images.length} images{isLoadingMore && ' (loading more...)'}
                </Typography>
            </Box>
            <TableContainer sx={{ flex: 1, minHeight: 0 }}>
                <Table stickyHeader size="small">
                    <TableHead>
                        <TableRow>
                            {COLUMNS.map(({ field, label }) => (
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
                        {rows.slice(page * rowsPerPage, (page + 1) * rowsPerPage).map((image) => (
                            <TableRow
                                key={image.oid}
                                hover
                                selected={currentImage?.oid === image.oid}
                                onClick={() => openImagePath(image, images, imageColumns.length, onImageClick)}
                                sx={{ cursor: 'pointer' }}
                            >
                                {COLUMNS.map(({ field, show }) => (
                                    <TableCell key={field} sx={{ whiteSpace: 'nowrap' }}>{show(image)}</TableCell>
                                ))}
                            </TableRow>
                        ))}
                        {rows.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={COLUMNS.length} align="center" sx={{ color: 'text.secondary', py: 4 }}>
                                    {images.length === 0 ? 'No images available' : 'No images match the current filters'}
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
            <TablePagination
                component="div"
                count={rows.length}
                page={Math.min(page, Math.max(0, Math.ceil(rows.length / rowsPerPage) - 1))}
                onPageChange={(_, next) => setPage(next)}
                rowsPerPage={rowsPerPage}
                rowsPerPageOptions={[25, 50, 100]}
                onRowsPerPageChange={(event) => {
                    setRowsPerPage(Number(event.target.value));
                    setPage(0);
                }}
                sx={{ flexShrink: 0, pr: 7 }}
            />
        </Box>
    );
};

export default ImageTable;
