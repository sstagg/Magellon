import React, { useState } from 'react';

interface SvgImageProps {
    width: number;
    height: number;
    imageUrl: string;
    imageStyle?: React.CSSProperties; // Optional style prop for the image
}

interface Point {
    x: number;
    y: number;
}

const SvgImage: React.FC<SvgImageProps> = ({ width, height, imageUrl, imageStyle }) => {
    const [circles, setCircles] = useState<Point[]>([]);

    const calculateAngle = (point1: Point, point2: Point): number => {
        return Math.atan2(point2.y - point1.y, point2.x - point1.x) * (180 / Math.PI);
    };

    const calculateMidpoint = (point1: Point, point2: Point): Point => {
        return {
            x: (point1.x + point2.x) / 2,
            y: (point1.y + point2.y) / 2,
        };
    };

    const calculateDistance = (point1: Point, point2: Point): number => {
        const dx = point2.x - point1.x;
        const dy = point2.y - point1.y;
        return Math.sqrt(dx * dx + dy * dy);
    };

    const handleSvgClick = (event: React.MouseEvent<SVGElement>) => {
        const svgRect = event.currentTarget.getBoundingClientRect();
        const x = event.clientX - svgRect.left;
        const y = event.clientY - svgRect.top;

        if (circles.length >= 2) {
            setCircles([{ x, y }]);
        } else {
            setCircles([...circles, { x, y }]);
        }
    };

    return (
        <svg width={width} height={height} onClick={handleSvgClick}>
            <image href={imageUrl} width={width} height={height} style={imageStyle}/> {/* Apply style here */}
            {circles.map((point, index) => (
                <circle key={index} cx={point.x} cy={point.y} r={5} fill="white"/>
            ))}
            {circles.length === 2 && (
                <>
                    <line
                        x1={circles[0].x}
                        y1={circles[0].y}
                        x2={circles[1].x}
                        y2={circles[1].y}
                        stroke="white"
                        strokeWidth={3}
                    />
                    <text
                        x={calculateMidpoint(circles[0], circles[1]).x}
                        y={calculateMidpoint(circles[0], circles[1]).y}
                        textAnchor="middle"
                        alignmentBaseline="middle"
                        fill="white"
                        fontSize="20" // Adjust font size as needed
                        transform={`rotate(${calculateAngle(circles[0], circles[1])}, ${calculateMidpoint(circles[0], circles[1]).x}, ${calculateMidpoint(circles[0], circles[1]).y}) translate(0, -2)`} // Move text 2 pixels above the line
                    >
                        {calculateDistance(circles[0], circles[1]).toFixed(2)}
                    </text>
                </>
            )}
        </svg>
    );
};

export default SvgImage;
