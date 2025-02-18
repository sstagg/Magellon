import { FC, useEffect } from 'react'
import {Grid, FormControl, InputLabel, MenuItem, Select, Stack} from '@mui/material'
import { useImageHierarchyStore } from '../store/useImageHierarchyStore'
import { ImageColumn } from './ImageColumn'
import ImageInfoDto, {SessionDto} from "../ImageInfoDto.ts";

interface ImageHierarchyViewerProps {
    sessions: SessionDto[]
    onImageSelect?: (image: ImageInfoDto, columnIndex: number) => void
}

export const ImageHierarchyViewer: FC<ImageHierarchyViewerProps> = ({
                                                                        sessions,
                                                                        onImageSelect
                                                                    }) => {
    const {
        sessionName,
        setSessionName,
        selectedImages,
        columns
    } = useImageHierarchyStore()

    useEffect(() => {
        if (onImageSelect) {
            const selectedImage = selectedImages.find(img => img !== null)
            if (selectedImage) {
                const columnIndex = selectedImages.findIndex(img => img?.oid === selectedImage.oid)
                onImageSelect(selectedImage, columnIndex)
            }
        }
    }, [selectedImages, onImageSelect])

    return (
        <Stack spacing={2}>
            <FormControl>
                <InputLabel>Session</InputLabel>
                <Select
                    value={sessionName || ''}
                    onChange={(e) => setSessionName(e.target.value)}
                >
                    {sessions.map((session) => (
                        <MenuItem key={session.Oid} value={session.name}>
                            {session.name}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            <Grid container spacing={2}>
                {columns.map((_, index) => (
                    <Grid item key={index}>
                        <ImageColumn columnIndex={index} />
                    </Grid>
                ))}
            </Grid>
        </Stack>
    )
}