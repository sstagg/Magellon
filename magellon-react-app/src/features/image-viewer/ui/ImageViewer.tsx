import React, { useEffect, useState } from 'react';
import { useAuthenticatedImage } from '../../../shared/lib/useAuthenticatedImage.ts';
import { DetectionResult, PtolemyDetection } from '../api/PtolemyDetectionService.ts';

interface ImageViewerProps {
    width: number;
    height: number;
    imageUrl: string;
    imageStyle?: React.CSSProperties;
    brightness?: number; // 0-100
    contrast?: number; // 0-100
    scale?: number; // 0.1-3
    detectionOverlay?: DetectionResult | null;
}

interface Point {
    x: number;
    y: number;
}

// Ptolemy stores vertices as [y, x] pairs (as_matrix_y layout).
// This helper maps one vertex to SVG coordinates given the source image dimensions.
function mrcToSvg(
    vy: number,
    vx: number,
    imgH: number,
    imgW: number,
    svgW: number,
    svgH: number,
): [number, number] {
    const uniformScale = Math.min(svgW / imgW, svgH / imgH);
    const offsetX = (svgW - imgW * uniformScale) / 2;
    const offsetY = (svgH - imgH * uniformScale) / 2;
    return [offsetX + vx * uniformScale, offsetY + vy * uniformScale];
}

function DetectionPolygons({
    detections,
    imageShape,
    svgW,
    svgH,
    category,
}: {
    detections: PtolemyDetection[];
    imageShape: number[];
    svgW: number;
    svgH: number;
    category: string;
}) {
    const [imgH, imgW] = imageShape;
    if (!imgH || !imgW) return null;

    const isHole = category === 'HoleDetection';
    const strokeColor = isHole ? '#00e5ff' : '#ffeb3b';

    // Ptolemy's PointSet2D.as_matrix_y() returns [col, row] pairs (its .y field
    // stores columns, .x stores rows — field names are inverted from convention).
    // Destructuring as [vy, vx] gives vy=col, vx=row; mrcToSvg expects (row, col).
    return (
        <>
            {detections.map((det, i) => {
                const svgPts = det.vertices.map(([vy, vx]) => mrcToSvg(vx, vy, imgH, imgW, svgW, svgH));
                const pointsStr = svgPts.map(([x, y]) => `${x},${y}`).join(' ');
                const [cx, cy] = mrcToSvg(det.center[1], det.center[0], imgH, imgW, svgW, svgH);
                const xs = svgPts.map(([x]) => x);
                const ys = svgPts.map(([, y]) => y);
                const boxW = Math.max(...xs) - Math.min(...xs);
                const boxH = Math.max(...ys) - Math.min(...ys);
                const tooLarge = boxW > svgW * 0.15 || boxH > svgH * 0.15;
                return (
                    <g key={i} opacity={0.85}>
                        {!tooLarge && (
                            <polygon
                                points={pointsStr}
                                fill="none"
                                stroke={strokeColor}
                                strokeWidth={1.5}
                            />
                        )}
                        <circle cx={cx} cy={cy} r={3} fill={strokeColor} opacity={0.9} />
                    </g>
                );
            })}
        </>
    );
}

const ImageViewer: React.FC<ImageViewerProps> = ({
                                                     width,
                                                     height,
                                                     imageUrl,
                                                     imageStyle,
                                                     brightness = 50,
                                                     contrast = 50,
                                                     scale = 1,
                                                     detectionOverlay,
                                                 }) => {
    const [circles, setCircles] = useState<Point[]>([]);

    // Use authenticated image hook to fetch the image with auth header
    const { imageUrl: authenticatedImageUrl, isLoading } = useAuthenticatedImage(imageUrl);

    useEffect(() => {
        // Reset circles when imageUrl changes
        setCircles([]);
    }, [imageUrl]);

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
        const svg = event.currentTarget;
        const pt = svg.createSVGPoint();
        pt.x = event.clientX;
        pt.y = event.clientY;

        // Transform the point to SVG coordinates
        const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());

        if (circles.length >= 2) {
            setCircles([{ x: svgP.x, y: svgP.y }]);
        } else {
            setCircles([...circles, { x: svgP.x, y: svgP.y }]);
        }
    };

    // Calculate brightness and contrast values for SVG filter
    const brightnessValue = brightness / 50; // 50 = 1 (normal)
    const contrastValue = contrast / 50; // 50 = 1 (normal)

    // Extract transform from imageStyle
    const getTransformMatrix = () => {
        let transformStr = '';
        const centerX = width / 2;
        const centerY = height / 2;

        // Start with translate to center
        transformStr += `translate(${centerX}, ${centerY}) `;

        // Apply scale
        transformStr += `scale(${scale}) `;

        // Apply any additional transforms from imageStyle
        if (imageStyle?.transform) {
            // Parse rotation
            const rotateMatch = imageStyle.transform.match(/rotate\((-?\d+)deg\)/);
            if (rotateMatch) {
                transformStr += `rotate(${rotateMatch[1]}) `;
            }

            // Parse horizontal flip
            if (imageStyle.transform.includes('scaleX(-1)')) {
                transformStr += 'scale(-1, 1) ';
            }

            // Parse vertical flip
            if (imageStyle.transform.includes('scaleY(-1)')) {
                transformStr += 'scale(1, -1) ';
            }
        }

        // Translate back
        transformStr += `translate(${-centerX}, ${-centerY})`;

        return transformStr;
    };

    const containerWidth = width * scale;
    const containerHeight = height * scale;

    const hasOverlay =
        detectionOverlay &&
        detectionOverlay.detections.length > 0 &&
        Array.isArray(detectionOverlay.image_shape) &&
        detectionOverlay.image_shape.length >= 2;

    return (
        <div style={{
            width: containerWidth,
            height: containerHeight,
            overflow: 'hidden',
            position: 'relative',
            display: 'inline-block'
        }}>
            <svg
                width={containerWidth}
                height={containerHeight}
                onClick={handleSvgClick}
                viewBox={`0 0 ${width} ${height}`}
                style={{ cursor: 'crosshair' }}
            >
                <defs>
                    <filter id="imageProcessing">
                        <feComponentTransfer>
                            <feFuncA type="table" tableValues="0 1" />
                            <feFuncR type="linear" slope={contrastValue} intercept={(1 - contrastValue) * 0.5} />
                            <feFuncG type="linear" slope={contrastValue} intercept={(1 - contrastValue) * 0.5} />
                            <feFuncB type="linear" slope={contrastValue} intercept={(1 - contrastValue) * 0.5} />
                        </feComponentTransfer>
                        <feComponentTransfer>
                            <feFuncR type="linear" slope={brightnessValue} />
                            <feFuncG type="linear" slope={brightnessValue} />
                            <feFuncB type="linear" slope={brightnessValue} />
                        </feComponentTransfer>
                    </filter>
                </defs>

                <g transform={getTransformMatrix()}>
                    {isLoading ? (
                        <rect
                            x="0"
                            y="0"
                            width={width}
                            height={height}
                            fill="#333"
                        />
                    ) : authenticatedImageUrl ? (
                        <image
                            href={authenticatedImageUrl}
                            x="0"
                            y="0"
                            width={width}
                            height={height}
                            filter="url(#imageProcessing)"
                            preserveAspectRatio="xMidYMid meet"
                            style={{
                                ...imageStyle,
                                transform: undefined, // Remove transform from style as we're using SVG transform
                                transition: 'none' // SVG transitions work differently
                            }}
                        />
                    ) : null}

                    {/* Detection overlay — rendered in the same transform group so
                        user zoom/flip/rotate applies uniformly */}
                    {hasOverlay && (
                        <DetectionPolygons
                            detections={detectionOverlay!.detections}
                            imageShape={detectionOverlay!.image_shape!}
                            svgW={width}
                            svgH={height}
                            category={detectionOverlay!.category}
                        />
                    )}
                </g>

                {/* Overlay for circles and measurements */}
                {circles.map((point, index) => (
                    <circle
                        key={index}
                        cx={point.x}
                        cy={point.y}
                        r={5}
                        fill="yellow"
                        stroke="black"
                        strokeWidth={2}
                        opacity={0.8}
                    />
                ))}

                {circles.length === 2 && (
                    <g>
                        <line
                            x1={circles[0].x}
                            y1={circles[0].y}
                            x2={circles[1].x}
                            y2={circles[1].y}
                            stroke="yellow"
                            strokeWidth={3}
                            opacity={0.8}
                        />
                        <line
                            x1={circles[0].x}
                            y1={circles[0].y}
                            x2={circles[1].x}
                            y2={circles[1].y}
                            stroke="black"
                            strokeWidth={1}
                            strokeDasharray="5 5"
                            opacity={0.8}
                        />

                        {/* Background for text */}
                        <rect
                            x={calculateMidpoint(circles[0], circles[1]).x - 40}
                            y={calculateMidpoint(circles[0], circles[1]).y - 25}
                            width="80"
                            height="25"
                            fill="black"
                            opacity={0.7}
                            rx="3"
                        />

                        <text
                            x={calculateMidpoint(circles[0], circles[1]).x}
                            y={calculateMidpoint(circles[0], circles[1]).y - 10}
                            textAnchor="middle"
                            alignmentBaseline="middle"
                            fill="yellow"
                            fontSize="16"
                            fontWeight="bold"
                            fontFamily="monospace"
                        >
                            {calculateDistance(circles[0], circles[1])?.toFixed(1)} px
                        </text>
                    </g>
                )}
            </svg>
        </div>
    );
};

export default ImageViewer;
