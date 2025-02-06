import {Grid, Paper, SelectChangeEvent, Stack} from "@mui/material";
import {ImageNavigatorComponent} from "../features/imageviewer/ImageNavigatorComponent.tsx";
import { SoloImageViewerComponent } from '../features/imageviewer/SoloImageViewerComponent.tsx';
import ImageInfoDto, {PagedImageResponse, SessionDto} from '../features/imageviewer/ImageInfoDto.ts';
import {useEffect, useState} from "react";
import {InfiniteData} from "react-query";
import {usePagedImages} from "../../../services/api/usePagedImagesHook.ts";
import {useAtlasImages} from "../../../services/api/FetchSessionAtlasImages.ts";
import {useSessionNames} from "../../../services/api/FetchUseSessionNames.ts";

export interface ImageColumnState {
    selectedImage: ImageInfoDto | null;
    caption: string;
    level: number;
    images:  InfiniteData<PagedImageResponse> | null;
}


const initialImageColumns: ImageColumnState[] = [
    {
        caption: "GR",
        level: 0,
        images: null,
        selectedImage: null,
    },
    {
        caption: "SQ",
        level: 1,
        images: null,
        selectedImage: null,
    },
    {
        caption: "HL",
        level: 2,
        images: null,
        selectedImage: null,
    },
    {
        caption: "EX",
        level: 3,
        images: null,
        selectedImage: null,
    },
];
export const ImagesPageView = () => {
    const [level, setLevel] = useState<number >(0);
    const [parentId, setParentId] = useState<string | null>(null);
    const [currentSession, setCurrentSession] = useState<SessionDto | null>(null);
    const [imageColumns, setImageColumns] = useState<(ImageColumnState)[]>(initialImageColumns);
    const [currentImage, setCurrentImage] = useState<ImageInfoDto | null>(null);

    const pageSize = 100;
    let sessionName = currentSession?.name;

    const { data: sessionData, isLoading: isSessionDataLoading, isError: isSessionError  } =  useSessionNames();
    const { data: atlasImages, isLoading: isAtlasLoading, isError: isAtlasError  } = useAtlasImages(sessionName,currentSession!==null);

    const OnCurrentImageChanged = (image: ImageInfoDto,column : number)  => {
        if (column === imageColumns.length) {
            return; // This is the last column; when an image is selected, nothing needs to be done
        }

        const updatedImageColumns = imageColumns.map((selectedColumn, index) => {
            if (index === column) {
                // Update the selectedImage property for the specified column
                return {
                    ...selectedColumn,
                    selectedImage: image,
                };
            } else if (index > column) {
                // Clear selectedImage for columns to the right
                return {
                    ...selectedColumn,
                    selectedImage: null, images: null
                };
            } else {
                // Keep the rest of the properties unchanged
                return selectedColumn;
            }
        });

        setImageColumns(updatedImageColumns);
        setCurrentImage(image);

    };
    const OnSessionSelected = (event: SelectChangeEvent) => {
        //debugger;
        const selectedValue = event.target.value;
        const sessionDto: SessionDto = {
            Oid: selectedValue,
            // Optionally, you can set the name property based on your requirements
            name: selectedValue,
        };
        setCurrentSession(sessionDto);
        setImageColumns(initialImageColumns);
        setCurrentImage(null);
    };

    const {
        data,error, isLoading,isSuccess, isError, refetch
        , fetchNextPage, hasNextPage,isFetching,isFetchingNextPage,
        status,
    } = usePagedImages({   sessionName ,parentId: parentId,pageSize, level    });

    useEffect(() => {
        //if there is selected image in current collumn , it would fetch data for next column using this column's oid as parent
        const getImageColumnsData = async (columnIndex) => {
            if(columnIndex==-1){
                setParentId(null);
                setLevel(0);
                const { data, isSuccess } = await refetch();

                if (isSuccess && data && data.pages && data.pages.length > 0) {
                    const updatedImageColumns = [...imageColumns];
                    updatedImageColumns[0] = {
                        ...updatedImageColumns[0], // Copy the existing properties
                        images: data, // Update the images property
                    };
                    setImageColumns(updatedImageColumns);
                }

            } else if (imageColumns[columnIndex].selectedImage && imageColumns[columnIndex].selectedImage?.children_count > 0) {
                setParentId(imageColumns[columnIndex].selectedImage?.oid);
                setLevel(columnIndex+1);

                // Refetch the data
                const { data, isSuccess } = await refetch();

                if (isSuccess && data && data.pages && data.pages.length > 0) {
                    const updatedImageColumns = [...imageColumns];
                    updatedImageColumns[columnIndex+1] = {
                        ...updatedImageColumns[columnIndex+1], // Copy the existing properties
                        images: data, // Update the images property
                    };
                    setImageColumns(updatedImageColumns);
                }
            }
        };

        // Handle the root column
        if(currentSession!==null){
            getImageColumnsData(-1);
        }

        // Loop through other columns
        for (let i = 0; i < imageColumns.length-1; i++) {
            if (imageColumns[i].selectedImage !==null && imageColumns[i].selectedImage?.oid !== null ) {
                getImageColumnsData(i);
            }
        }
    }, [currentImage?.oid, level, data, isSuccess,currentSession]);

    return (
        <Grid container>
            <Grid item xs={5}>
                <ImageNavigatorComponent onImageClick={OnCurrentImageChanged} selectedSession={currentSession} OnSessionSelected={OnSessionSelected} selectedImage={currentImage} ImageColumns={imageColumns} Sessions={sessionData} Atlases={atlasImages}/>
            </Grid>
            <Grid item  xs={7}>
                <SoloImageViewerComponent selectedImage={currentImage}/>
            </Grid>
        </Grid>
    );
};
