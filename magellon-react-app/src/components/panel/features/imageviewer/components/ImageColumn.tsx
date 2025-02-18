import { FC } from 'react'
import { Stack, CircularProgress, Alert } from '@mui/material'
import { useImageHierarchyStore } from '../store/useImageHierarchyStore'
import {ThumbImage} from "./ThumbImage.tsx";

interface ImageColumnProps {
    columnIndex: number
}

export const ImageColumn: FC<ImageColumnProps> = ({ columnIndex }) => {
    const { columns, selectedImages, selectImage } = useImageHierarchyStore()
    const column = columns[columnIndex]

    if (column.isLoading) {
        return (
            <Stack alignItems="center" spacing={2}>
                <CircularProgress />
                <div>Loading {column.caption}...</div>
            </Stack>
        )
    }

    if (column.error) {
        return (
            <Alert severity="error">
                Error loading {column.caption}: {column.error.message}
            </Alert>
        )
    }

    return (
        <Stack spacing={1} width={170}>
            <h3>{column.caption}</h3>
            {column.images.map((image) => (
                <ThumbImage
                    key={image.oid}
                    image={image}
                    isSelected={selectedImages[columnIndex]?.oid === image.oid}
                    onImageClick={() => selectImage(image, columnIndex)}
                    level={column.level}
                />
            ))}
        </Stack>
    )
}
