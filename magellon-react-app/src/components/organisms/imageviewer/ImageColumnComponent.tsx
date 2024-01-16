import ImageInfoDto from "./ImageInfoDto.ts";
import {ImagesStackComponent} from "./ImagesStackComponent.tsx";
import {usePagedImages} from "../../../services/api/usePagedImagesHook.ts";
import {useEffect, useState} from "react";

interface ImageColumnProps {
    onImageClick: (imageInfo: ImageInfoDto) => void;
    parentImage: ImageInfoDto | null;
    sessionName: string;
    caption: string;
    level: number;
}


export const ImageColumnComponent = ({ onImageClick , parentImage ,sessionName, level,caption} : ImageColumnProps) => {
    const [parentId, setParentId] = useState<string | null>(null);
    // console.log(`level: ${level} start`);
    const pageSize = 5;
    const idName=caption;
    useEffect(() => {
        const parentImageLevel = parentImage?.level ?? 0;

        if (parentImage && parentImageLevel === level - 1 ) {
            setParentId(parentImage.oid);
        } else {
            setParentId(null);
        }
        refetch();
    }, [parentImage, level]);

    const {
        data,error, isLoading,isSuccess, isError, refetch
        , fetchNextPage, hasNextPage,isFetching,isFetchingNextPage,
        status,
    } = usePagedImages({   sessionName,parentId,pageSize,level ,  idName   });


     // console.log(`level: ${level} step ${(parentImage?.children_count || 0) > 0}`);
    // const shouldLoad =(level === 0 && parentImage === null) ||  ((parentImage?.level|| 0)+ 1 === level  && (parentImage?.children_count || 0) > 0);
    //console.log(`ImageColumnComponent.useEffect2 > shouldLoad: ${shouldLoad},  sessionName: ${sessionName}, level: ${level}, parentImage: ${JSON.stringify(parentImage)}, data: ${JSON.stringify(data)}`);

    if (isLoading===null || isLoading) {
        return <div>Loading...</div>;
    }
    if (error) {
        return <div>Error: {error.message}</div>;
    }

    return (
        <>
            {isSuccess &&  data?.pages ? (
                <ImagesStackComponent caption={caption} images={data} level={level} onImageClick={onImageClick} />
            ) : null}
        </>
    );
};
