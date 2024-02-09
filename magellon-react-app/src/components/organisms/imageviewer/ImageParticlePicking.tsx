import React, { useState } from 'react';

interface ImageParticlePickingProps {
    imageUrl: string;
    width: number;
    height: number;
    onCirclesSelected: (circles: Point[]) => void;
}

interface Point {
    x: number;
    y: number;
}

const ImageParticlePicking: React.FC<ImageParticlePickingProps> = ({ imageUrl, width, height, onCirclesSelected }) => {
    const [circles, setCircles] = useState<Point[]>([]);
    const [selectedCircleIndex, setSelectedCircleIndex] = useState<number | null>(null);

    // const [isDrawing, setIsDrawing] = useState<boolean>(false);
    const handleSvgClick2 = (event: React.MouseEvent<SVGElement>) => {
        const svgRect = event.currentTarget.getBoundingClientRect();
        const x = event.clientX - svgRect.left;
        const y = event.clientY - svgRect.top;

        setCircles([...circles, { x, y }]);



    };
    const handleSvgClick = (event: React.MouseEvent<SVGElement>) => {
        const svgRect = event.currentTarget.getBoundingClientRect();
        const x = event.clientX - svgRect.left;
        const y = event.clientY - svgRect.top;
        // console.log("Handle clicked");
       setCircles([...circles, { x, y }]);
        // Check if any circle is clicked
        // const clickedCircleIndex = circles.findIndex(circle => {
        //     const dx = circle.x - x;
        //     const dy = circle.y - y;
        //     return dx * dx + dy * dy <= 15 * 15;
        // });
        //
        // setSelectedCircleIndex(clickedCircleIndex);
        // console.log("Circle clicked",clickedCircleIndex);
    };
    const handleCircleClick = (index: number) => {
        console.log("Circle clicked",index);
        setSelectedCircleIndex(index);
    };

    const handleDeleteButtonClick = () => {
        if (selectedCircleIndex !== null) {
            const updatedCircles = circles.filter((_, index) => index !== selectedCircleIndex);
            setCircles(updatedCircles);
            setSelectedCircleIndex(null);
        }
    };
    const handleSvgMouseDown = (event: React.MouseEvent<SVGElement>) => {

    };

    const handleSvgMouseMove = (event: React.MouseEvent<SVGElement>) => {

    };

    const handleSvgMouseUp = () => {

    };

    return (
        <svg
            width={width}
            height={height}
            // onMouseDown={handleSvgMouseDown}
            // onMouseMove={handleSvgMouseMove}
            // onMouseUp={handleSvgMouseUp}
            onClick={handleSvgClick}
        >
            <image href={imageUrl} width={width} height={height} />
            {circles.map((point, index) => (
                <g key={index}>
                    <circle
                        cx={point.x}
                        cy={point.y}
                        r={15}
                        fill={selectedCircleIndex === index ? 'seasaltblue' : 'none'}
                        stroke={selectedCircleIndex === index ? 'gray' : 'white'}
                        strokeWidth={2}
                        onClick={() => handleCircleClick(index)}
                    />
                    <line x1={point.x - 5} y1={point.y} x2={point.x + 5} y2={point.y} stroke="white" strokeWidth={2}/>
                    <line x1={point.x} y1={point.y - 5} x2={point.x} y2={point.y + 5} stroke="white" strokeWidth={2}/>
                </g>
            ))}
        </svg>

    );
};

export default ImageParticlePicking;
