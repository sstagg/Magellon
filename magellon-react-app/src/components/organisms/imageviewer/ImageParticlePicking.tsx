import React, {useEffect, useState} from 'react';
import ImageInfoDto from "./ImageInfoDto.ts";
import {ParticlePickingDto} from "../../../domains/ParticlePickingDto.ts";

interface ImageParticlePickingProps {
    imageUrl: string;
    width: number;
    height: number;
    image:ImageInfoDto | null;
    ipp :ParticlePickingDto |null;
    onCirclesSelected: (circles: Point[]) => void;
    onIppUpdate: (updatedIpp: ParticlePickingDto) => void;
}

interface Point {
    x: number;
    y: number;
}

// enum State {
//     Add = 'Add',
//     Edit = 'Edit',
//     Remove = 'Remove'
// }


const ImageParticlePicking: React.FC<ImageParticlePickingProps> = ({ imageUrl,image,ipp, width, height, onCirclesSelected ,onIppUpdate}) => {
    // const [tool, setTool] = useState<State>(State.Add);
    const [circles, setCircles] = useState<Point[]>([]);
    const [selectedCircleIndex, setSelectedCircleIndex] = useState<number | null>(null);
    const radius = 10;


    useEffect(() => {
        // debugger;
        if (ipp && ipp?.data_json) {

            // If there are existing circles in ipp.temp, parse and set them in the state
            const parsedCircles: Point[] = (ipp.data_json);
            setCircles(parsedCircles);
        }else{
            setCircles([])
        }
    }, [ipp?.oid]);

    // useEffect(() => {
    //     // Reset circles when imageUrl changes
    //     setCircles([]);
    // }, [imageUrl]);


    const handleSvgClick = (event: React.MouseEvent<SVGElement>) => {
        const svgRect = event.currentTarget.getBoundingClientRect();
        const x = event.clientX - svgRect.left;
        const y = event.clientY - svgRect.top;
        // console.log("Handle clicked");

        if (event.button === 0 && !(event.ctrlKey || event.metaKey)) { // Left click
            setCircles([...circles, { x, y }]);
        } else if (event.button === 0 && (event.ctrlKey || event.metaKey))  { // Right click
            const clickedCircleIndex = circles.findIndex(circle => {
                const dx = circle.x - x;
                const dy = circle.y - y;

                return dx * dx + dy * dy <= radius * radius;
            });

            if (clickedCircleIndex !== -1) {
                const updatedCircles = circles.filter((_, i) => i !== clickedCircleIndex);
                setCircles(updatedCircles);
                setSelectedCircleIndex(null);
            }
        }
        const updatedIpp = { ...ipp, temp: JSON.stringify(circles) };
        onIppUpdate(updatedIpp);

    };
    // const handleCircleClick = (index: number) => {
    //     console.log("Circle clicked",index);
    //     setSelectedCircleIndex(index);
    // };



    return (
        <>
            <svg
                width={width}
                height={height}
                // onMouseDown={handleSvgMouseDown}
                // onMouseMove={handleSvgMouseMove}
                // onMouseUp={handleSvgMouseUp}
                onClick={handleSvgClick}
            >

                <image href={imageUrl} width={width} height={height}/>
                {circles.map((point, index) => (
                    <g key={index}>
                        <circle
                            cx={point.x}
                            cy={point.y}
                            r={radius}
                            fill={selectedCircleIndex === index ? 'seasaltblue' : 'none'}
                            stroke={selectedCircleIndex === index ? 'gray' : 'white'}
                            strokeWidth={2}
                            // onClick={() => handleCircleClick(index)}
                        />
                        <line x1={point.x - 5} y1={point.y} x2={point.x + 5} y2={point.y} stroke="white"
                              strokeWidth={2}/>
                        <line x1={point.x} y1={point.y - 5} x2={point.x} y2={point.y + 5} stroke="white"
                              strokeWidth={2}/>
                    </g>
                ))}
                <text x="10" y="20" fill="white">
                    {circles.length > 0 ? JSON.stringify(circles) : "No circles"}
                </text>
            </svg>

        </>

    );
};

export default ImageParticlePicking;
