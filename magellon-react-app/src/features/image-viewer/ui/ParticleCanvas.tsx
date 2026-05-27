import React, { useState, useRef, useEffect, useCallback } from 'react';
import { alpha } from '@mui/material';
import { useAuthenticatedImage } from '../../../shared/lib/useAuthenticatedImage.ts';
import type { Point, ParticleClass, Tool } from '../lib/useParticleOperations.ts';

interface ParticleCanvasProps {
    imageUrl: string;
    width: number;
    height: number;
    particles: Point[];
    selectedParticles: Set<string>;
    tool: Tool;
    particleRadius: number;
    particleOpacity: number;
    showGrid: boolean;
    showCrosshair: boolean;
    zoom: number;
    activeClass: string;
    particleClasses: ParticleClass[];
    onParticlesUpdate: (particles: Point[]) => void;
    onSelectedParticlesUpdate: (selected: Set<string>) => void;
    onShowSnackbar: (message: string, severity: 'success' | 'error' | 'info' | 'warning') => void;
    /** Called when the underlying image reports its natural dimensions. */
    onImageNaturalSize?: (shape: [number, number]) => void;
}

const MINI_W = 150;

/** Ray-casting point-in-polygon test. */
function isPointInPolygon(point: Point, polygon: Point[]): boolean {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].x, yi = polygon[i].y;
        const xj = polygon[j].x, yj = polygon[j].y;
        const intersect =
            yi > point.y !== yj > point.y &&
            point.x < ((xj - xi) * (point.y - yi)) / (yj - yi) + xi;
        if (intersect) inside = !inside;
    }
    return inside;
}

export const ParticleCanvas: React.FC<ParticleCanvasProps> = ({
    imageUrl,
    width,
    height,
    particles,
    selectedParticles,
    tool,
    particleRadius,
    particleOpacity,
    showGrid,
    showCrosshair,
    zoom,
    activeClass,
    particleClasses,
    onParticlesUpdate,
    onSelectedParticlesUpdate,
    onShowSnackbar,
    onImageNaturalSize,
}) => {
    const svgRef = useRef<SVGSVGElement>(null);
    const minimapRef = useRef<HTMLCanvasElement>(null);

    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isPanning, setIsPanning] = useState(false);
    const [dragStart, setDragStart] = useState<Point | null>(null);
    const [boxSelection, setBoxSelection] = useState<{ start: Point; end: Point } | null>(null);
    const [hoveredParticle, setHoveredParticle] = useState<string | null>(null);

    // Hover ring cursor tracking
    const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);

    // Lasso selection
    const [isLassoing, setIsLassoing] = useState(false);
    const [lassoPath, setLassoPath] = useState<Point[]>([]);

    const { imageUrl: authenticatedImageUrl, isLoading: isImageLoading } = useAuthenticatedImage(imageUrl);

    useEffect(() => {
        if (!authenticatedImageUrl || !onImageNaturalSize) return;
        const probe = new Image();
        probe.addEventListener('load', () => {
            if (probe.naturalWidth > 0 && probe.naturalHeight > 0) {
                onImageNaturalSize([probe.naturalHeight, probe.naturalWidth]);
            }
        });
        probe.src = authenticatedImageUrl;
    }, [authenticatedImageUrl, onImageNaturalSize]);

    // Minimap draw
    useEffect(() => {
        const canvas = minimapRef.current;
        if (!canvas || !authenticatedImageUrl || width === 0 || height === 0) return;

        const miniH = Math.max(1, Math.round((height / width) * MINI_W));
        canvas.width = MINI_W;
        canvas.height = miniH;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const scaleX = MINI_W / width;
        const scaleY = miniH / height;

        const img = new Image();
        img.onload = () => {
            ctx.clearRect(0, 0, MINI_W, miniH);
            ctx.drawImage(img, 0, 0, MINI_W, miniH);

            // Particle dots
            particles.forEach((p) => {
                const pc = particleClasses.find((c) => c.id === p.class);
                ctx.fillStyle = pc?.color ?? '#4caf50';
                ctx.beginPath();
                ctx.arc(p.x * scaleX, p.y * scaleY, 2, 0, Math.PI * 2);
                ctx.fill();
            });

            // Viewport indicator
            const vx = (-pan.x / zoom) * scaleX;
            const vy = (-pan.y / zoom) * scaleY;
            const vw = (width / zoom) * scaleX;
            const vh = (height / zoom) * scaleY;

            ctx.fillStyle = 'rgba(33,150,243,0.12)';
            ctx.fillRect(vx, vy, vw, vh);
            ctx.strokeStyle = '#2196f3';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(vx, vy, vw, vh);
        };
        img.src = authenticatedImageUrl;
    }, [pan, zoom, particles, authenticatedImageUrl, width, height, particleClasses]);

    const generateId = () => `particle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const getSVGPoint = useCallback((e: React.MouseEvent<SVGElement>): Point => {
        if (!svgRef.current) return { x: 0, y: 0 };
        const svg = svgRef.current;
        const pt = svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());
        return { x: svgP.x, y: svgP.y };
    }, []);

    const handleMouseDown = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);

        if (tool === 'pan' || e.button === 1 || (e.button === 0 && e.altKey)) {
            setIsPanning(true);
            setDragStart(point);
        } else if (tool === 'box') {
            setBoxSelection({ start: point, end: point });
        } else if (tool === 'lasso') {
            setIsLassoing(true);
            setLassoPath([point]);
        }
    };

    const handleMouseMove = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);
        setCursorPos(point);

        if (isPanning && dragStart) {
            const dx = point.x - dragStart.x;
            const dy = point.y - dragStart.y;
            setPan((prev) => ({ x: prev.x + dx * zoom, y: prev.y + dy * zoom }));
            setDragStart(point);
        } else if (boxSelection) {
            setBoxSelection((prev) => (prev ? { ...prev, end: point } : null));
        } else if (isLassoing) {
            setLassoPath((prev) => [...prev, point]);
        }
    };

    const handleMouseLeave = () => {
        setCursorPos(null);
    };

    const handleMouseUp = () => {
        setIsPanning(false);
        setDragStart(null);

        if (boxSelection) {
            const minX = Math.min(boxSelection.start.x, boxSelection.end.x);
            const maxX = Math.max(boxSelection.start.x, boxSelection.end.x);
            const minY = Math.min(boxSelection.start.y, boxSelection.end.y);
            const maxY = Math.max(boxSelection.start.y, boxSelection.end.y);

            const selected = new Set<string>();
            particles.forEach((p) => {
                if (p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY) {
                    selected.add(p.id || '');
                }
            });

            onSelectedParticlesUpdate(selected);
            setBoxSelection(null);
            if (selected.size > 0) {
                onShowSnackbar(`Selected ${selected.size} particles`, 'info');
            }
        }

        if (isLassoing) {
            if (lassoPath.length > 2) {
                const selected = new Set<string>();
                particles.forEach((p) => {
                    if (isPointInPolygon(p, lassoPath)) selected.add(p.id || '');
                });
                onSelectedParticlesUpdate(selected);
                if (selected.size > 0) {
                    onShowSnackbar(`Selected ${selected.size} particles`, 'info');
                }
            }
            setIsLassoing(false);
            setLassoPath([]);
        }
    };

    const handleClick = (e: React.MouseEvent<SVGElement>) => {
        if (isPanning || boxSelection || isLassoing) return;

        const point = getSVGPoint(e);

        switch (tool) {
            case 'add':
                addParticle(point);
                break;
            case 'remove':
                removeParticleAt(point);
                break;
            case 'select':
                toggleParticleSelection(point);
                break;
        }
    };

    const addParticle = (point: Point) => {
        const newParticle: Point = {
            ...point,
            id: generateId(),
            type: 'manual',
            confidence: 1,
            class: activeClass,
            timestamp: Date.now(),
        };
        onParticlesUpdate([...particles, newParticle]);
    };

    const removeParticleAt = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            onParticlesUpdate(particles.filter((p) => p.id !== clickedParticle.id));
        }
    };

    const toggleParticleSelection = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            const newSelected = new Set(selectedParticles);
            if (newSelected.has(clickedParticle.id || '')) {
                newSelected.delete(clickedParticle.id || '');
            } else {
                newSelected.add(clickedParticle.id || '');
            }
            onSelectedParticlesUpdate(newSelected);
        }
    };

    const findParticleAt = (point: Point): Point | null => {
        return (
            particles.find((p) => {
                const dx = p.x - point.x;
                const dy = p.y - point.y;
                return Math.sqrt(dx * dx + dy * dy) <= particleRadius;
            }) || null
        );
    };

    const getParticleColor = (particle: Point) => {
        const particleClass = particleClasses.find((c) => c.id === particle.class);
        const baseColor = particleClass?.color || '#4caf50';
        if (selectedParticles.has(particle.id || '')) return '#2196f3';
        if (hoveredParticle === particle.id) return '#ff9800';
        return baseColor;
    };

    const viewBox = `${-pan.x / zoom} ${-pan.y / zoom} ${width / zoom} ${height / zoom}`;

    const cursorStyle =
        tool === 'add' ? 'crosshair' :
        tool === 'move' || tool === 'pan' ? 'move' :
        tool === 'lasso' ? 'crosshair' :
        tool === 'select' ? 'pointer' :
        'default';

    // Lasso SVG points string
    const lassoPoints = lassoPath.map((p) => `${p.x},${p.y}`).join(' ');

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <svg
                ref={svgRef}
                width="100%"
                height="100%"
                viewBox={viewBox}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
                onContextMenu={(e) => e.preventDefault()}
                style={{ cursor: cursorStyle, backgroundColor: '#000', display: 'block' }}
            >
                {/* Grid */}
                {showGrid && (
                    <g opacity={0.2}>
                        <defs>
                            <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
                                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="white" strokeWidth="1" />
                            </pattern>
                        </defs>
                        <rect width="100%" height="100%" fill="url(#grid)" />
                    </g>
                )}

                {/* Image */}
                {isImageLoading ? (
                    <rect width={width} height={height} fill="#333" />
                ) : authenticatedImageUrl ? (
                    <image href={authenticatedImageUrl} width={width} height={height} />
                ) : null}

                {/* Particles */}
                <g>
                    {particles.map((particle) => {
                        const particleClass = particleClasses.find((c) => c.id === particle.class);
                        if (!particleClass?.visible) return null;

                        return (
                            <g
                                key={particle.id}
                                onMouseEnter={() => setHoveredParticle(particle.id || null)}
                                onMouseLeave={() => setHoveredParticle(null)}
                            >
                                <circle
                                    cx={particle.x}
                                    cy={particle.y}
                                    r={particleRadius}
                                    fill="none"
                                    stroke={getParticleColor(particle)}
                                    strokeWidth={selectedParticles.has(particle.id || '') ? 3 : 2}
                                    opacity={particleOpacity}
                                    vectorEffect="non-scaling-stroke"
                                />

                                {showCrosshair && (
                                    <>
                                        <line
                                            x1={particle.x - particleRadius / 2}
                                            y1={particle.y}
                                            x2={particle.x + particleRadius / 2}
                                            y2={particle.y}
                                            stroke={getParticleColor(particle)}
                                            strokeWidth={2}
                                            opacity={particleOpacity}
                                            vectorEffect="non-scaling-stroke"
                                        />
                                        <line
                                            x1={particle.x}
                                            y1={particle.y - particleRadius / 2}
                                            x2={particle.x}
                                            y2={particle.y + particleRadius / 2}
                                            stroke={getParticleColor(particle)}
                                            strokeWidth={2}
                                            opacity={particleOpacity}
                                            vectorEffect="non-scaling-stroke"
                                        />
                                    </>
                                )}

                                {particle.type === 'auto' && particle.confidence && particle.confidence > 0 && (
                                    <circle
                                        cx={particle.x}
                                        cy={particle.y}
                                        r={particleRadius * 0.15}
                                        fill={getParticleColor(particle)}
                                        opacity={Math.min(particle.confidence, 1)}
                                    />
                                )}
                            </g>
                        );
                    })}
                </g>

                {/* Hover ring — shows pick radius in add/remove mode */}
                {cursorPos && (tool === 'add' || tool === 'remove') && (
                    <circle
                        cx={cursorPos.x}
                        cy={cursorPos.y}
                        r={particleRadius}
                        fill={tool === 'add' ? 'rgba(76,175,80,0.08)' : 'rgba(244,67,54,0.08)'}
                        stroke={tool === 'add' ? '#4caf50' : '#f44336'}
                        strokeWidth={1.5}
                        strokeDasharray="5 3"
                        opacity={0.75}
                        vectorEffect="non-scaling-stroke"
                        style={{ pointerEvents: 'none' }}
                    />
                )}

                {/* Box Selection */}
                {boxSelection && (
                    <rect
                        x={Math.min(boxSelection.start.x, boxSelection.end.x)}
                        y={Math.min(boxSelection.start.y, boxSelection.end.y)}
                        width={Math.abs(boxSelection.end.x - boxSelection.start.x)}
                        height={Math.abs(boxSelection.end.y - boxSelection.start.y)}
                        fill={alpha('#2196f3', 0.2)}
                        stroke="#2196f3"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        vectorEffect="non-scaling-stroke"
                    />
                )}

                {/* Lasso selection in progress */}
                {isLassoing && lassoPath.length > 1 && (
                    <polygon
                        points={lassoPoints}
                        fill={alpha('#ff9800', 0.15)}
                        stroke="#ff9800"
                        strokeWidth={1.5}
                        strokeDasharray="6 3"
                        vectorEffect="non-scaling-stroke"
                        style={{ pointerEvents: 'none' }}
                    />
                )}
            </svg>

            {/* Minimap overlay — bottom-left, pointer-events off so it doesn't block canvas */}
            <canvas
                ref={minimapRef}
                style={{
                    position: 'absolute',
                    bottom: 8,
                    left: 8,
                    border: '1px solid rgba(255,255,255,0.25)',
                    borderRadius: 4,
                    opacity: 0.85,
                    pointerEvents: 'none',
                    display: zoom === 1 && pan.x === 0 && pan.y === 0 ? 'none' : 'block',
                }}
            />
        </div>
    );
};
