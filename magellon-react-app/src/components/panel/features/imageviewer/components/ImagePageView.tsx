import { FC, useState } from 'react'
import { Grid } from '@mui/material'
import { ImageHierarchyViewer } from './ImageHierarchyViewer'
import { SoloImageViewerComponent } from '../SoloImageViewerComponent'
import { useQuery } from 'react-query'
import ImageInfoDto from "../ImageInfoDto.ts";


export const ImagesPageView: FC = () => {
    const [selectedImage, setSelectedImage] = useState<ImageInfoDto | null>(null)

    const { data: sessions, isLoading, error } = useQuery('sessions', fetchSessions)

    if (isLoading) return <div>Loading sessions...</div>
    if (error) return <div>Error loading sessions</div>
    if (!sessions) return <div>No sessions found</div>

    return (
        <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
                <ImageHierarchyViewer
                    sessions={sessions}
                    onImageSelect={(image) => setSelectedImage(image)}
                />
            </Grid>

            <Grid item xs={12} md={8}>
                {selectedImage && (
                    <SoloImageViewerComponent selectedImage={selectedImage} />
                )}
            </Grid>
        </Grid>
    )
}