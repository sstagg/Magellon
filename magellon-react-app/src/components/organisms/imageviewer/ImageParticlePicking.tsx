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
    // const [isDrawing, setIsDrawing] = useState<boolean>(false);
    const handleSvgClick = (event: React.MouseEvent<SVGElement>) => {
        const svgRect = event.currentTarget.getBoundingClientRect();
        const x = event.clientX - svgRect.left;
        const y = event.clientY - svgRect.top;

        setCircles([...circles, { x, y }]);
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
                    <circle cx={point.x} cy={point.y} r={15} fill="none" stroke="white" strokeWidth={2} />
                    <line x1={point.x - 5} y1={point.y} x2={point.x + 5} y2={point.y} stroke="white" strokeWidth={2} />
                    <line x1={point.x} y1={point.y - 5} x2={point.x} y2={point.y + 5} stroke="white" strokeWidth={2} />
                </g>
            ))}
        </svg>
    );
};

export default ImageParticlePicking;
