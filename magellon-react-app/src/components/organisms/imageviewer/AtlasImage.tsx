import React, {useEffect, useState} from 'react'
import ImageInfoDto from "./ImageInfoDto.ts";
import {settings} from "../../../core/settings.ts";

const BASE_URL = settings.ConfigData.SERVER_WEB_API_URL ;

export interface ImageMapArea {
    shape: string;
    coords: string;
    alt: string;
    "data-name": string;
    "data-id": string;
}

export interface ImageMap {
    name: string;
    areas: ImageMapArea[];
}
interface AtlasPictureProps {
    name: string | undefined;
    imageMapJson: string | undefined;
    onImageClick: (imageInfo: ImageInfoDto, column : number) => void;
    // imageMap: ImageMap | null;
    finalWidth: number;
    finalHeight: number;
    backgroundColor: string;
}

function getImageNumber(input: string): number | null {
    // Use a regular expression to match the numeric part
    const match = input.match(/(\d+)gr/);

    // Check if a match is found
    if (match) {
        // Convert the matched string to a number and return it
        return parseInt(match[0], 10);
    } else {
        // If no match is found, return null or handle the error as needed
        return null;
    }
}

interface ApiResponse {
    result: ImageInfoDto;
}
export default function AtlasImage({ name, finalWidth , finalHeight ,backgroundColor, imageMapJson , onImageClick} :AtlasPictureProps) {

    // const { areas } = imageMap;
    const [imageMap, setImageMap] = useState<ImageMap | null>(null);
    const [hoveredArea, setHoveredArea] = useState<string | null>(null);
    const [selectedArea, setSelectedArea] = useState<string | null>(null);


    useEffect(() => {
        if (imageMapJson) {
            try {
                const parsedImageMap: ImageMap = JSON.parse(imageMapJson);
                setImageMap(parsedImageMap);
            } catch (error) {
                console.error('Error parsing image map JSON:', error);
            }
        }
    }, [imageMapJson]);

    const handleMouseOver = (areaName: string) => {
        setHoveredArea(areaName);
    };

    const handleMouseOut = () => {
        setHoveredArea(null);
    };

    const handleImageClick = async (area: ImageMapArea) => {
        const areaName = area['data-name'];
        setSelectedArea((prevSelectedArea) => (prevSelectedArea === areaName ? null : areaName));
        try {
            const response = await fetch(`${BASE_URL}/images/${areaName}`);
            if (!response.ok) {
                throw new Error('Image not found');
            }
            const data: ApiResponse = await response.json();
            onImageClick(data.result,0);
            // console.log(data.result);

        } catch (error) {
            console.error('Error fetching image details:', error);
        }

        console.log(areaName);
    };


    const renderRectangles = () => {
        return imageMap?.areas.map((area, index) => {
            const [x1, y1, width, height] = area.coords
                .split(' ')
                .map((coord) => (Number(coord) / 1600) * finalWidth) as [
                number,
                number,
                number,
                number
            ];

            const circleRadius = (60 / 1600) * finalWidth;
            const textFontSize = (80 / 1600) * finalWidth;

            return (
                <g
                    key={`image-group-${index}`}
                    onClick={() => handleImageClick(area)}
                    style={{
                        cursor: 'pointer',
                    }}
                >
                    <image
                        x={x1}
                        y={y1}
                        width={width }
                        height={height }
                        href={`${BASE_URL}/image_thumbnail?name=${area['data-name']}`} // Assuming 'data-name' contains the image source
                        data-name={area['data-name']}
                        // data-id={area['data-id']}
                        onMouseOver={() => handleMouseOver(area['data-name'])}
                        onMouseOut={handleMouseOut}
                        // onClick={() => handleImageClick(area['data-name'])}
                        onClick={() => handleImageClick(area)}
                        style={{
                            // filter: 'drop-shadow(0px 0px 1px white)',
                            outline:
                                (hoveredArea === area['data-name'] || selectedArea === area['data-name']) ? '3px solid white':'',
                            opacity: hoveredArea === area['data-name'] ? 0.7 : 1,
                            cursor: 'pointer',
                            borderRadius: '5px',
                        }}
                    />
                    {hoveredArea === area['data-name'] && (
                        <g style={{ pointerEvents: 'none' }}>
                            <circle
                                cx={x1 + width / 2}
                                cy={y1 + height / 2}
                                r={circleRadius}
                                fill="orange"
                            />
                            <text
                                key={`text-${index}`}
                                x={(x1) + (width / 2)}
                                y={y1 + height / 2 + textFontSize / 3}
                                textAnchor="middle"
                                fill="white"
                                fontSize={`${textFontSize}px`} // Adjust the font size
                                 >
                                {getImageNumber(area['data-name'])}
                            </text>
                        </g>
                        )}
                </g>
            );
        });
    };
    return (
        <svg width={finalWidth} height={finalHeight} xmlns="http://www.w3.org/2000/svg">
            <rect width="100%" height="100%" fill={backgroundColor}  />
            {/*<image width="100%" height="100%"  href={`http://127.0.0.1:8000/web/atlas-image?name=${name}`} />*/}
            {renderRectangles()}
        </svg>
    );

}
