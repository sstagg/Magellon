import React, { useState, useRef, useEffect } from 'react';
import { alpha } from '@mui/material';
import { useAuthenticatedImage } from '../../../shared/lib/useAuthenticatedImage.ts';
import { Point, ParticleClass, Tool } from '../lib/useParticleOperations.ts';

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

// Enhanced Particle Editor Component (SVG canvas)
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
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isPanning, setIsPanning] = useState(false);
    const [dragStart, setDragStart] = useState<Point | null>(null);
    const [boxSelection, setBoxSelection] = useState<{ start: Point; end: Point } | null>(null);
    const [hoveredParticle, setHoveredParticle] = useState<string | null>(null);

    const { imageUrl: authenticatedImageUrl, isLoading: isImageLoading } = useAuthenticatedImage(imageUrl);

    // Detect the thumbnail's natural dimensions and report upward — so the
    // parent can size its coord space to the actual image when backend
    // didn't supply an image_shape.
    useEffect(() => {
        if (!authenticatedImageUrl || !onImageNaturalSize) return;
        const probe = new Image();
        probe.onload = () => {
            if (probe.naturalWidth > 0 && probe.naturalHeight > 0) {
                onImageNaturalSize([probe.naturalHeight, probe.naturalWidth]);
            }
        };
        probe.src = authenticatedImageUrl;
    }, [authenticatedImageUrl, onImageNaturalSize]);

    const generateId = () => `particle-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const getSVGPoint = (e: React.MouseEvent<SVGElement>): Point => {
        if (!svgRef.current) return { x: 0, y: 0 };

        const svg = svgRef.current;
        const pt = svg.createSVGPoint();
        pt.x = e.clientX;
        pt.y = e.clientY;
        const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());

        return { x: svgP.x, y: svgP.y };
    };

    const handleMouseDown = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);

        if (tool === 'pan' || (e.button === 1) || (e.button === 0 && e.altKey)) {
            setIsPanning(true);
            setDragStart(point);
        } else if (tool === 'box') {
            setBoxSelection({ start: point, end: point });
        }
    };

    const handleMouseMove = (e: React.MouseEvent<SVGElement>) => {
        const point = getSVGPoint(e);

        if (isPanning && dragStart) {
            const dx = point.x - dragStart.x;
            const dy = point.y - dragStart.y;
            setPan(prev => ({
                x: prev.x + dx * zoom,
                y: prev.y + dy * zoom
            }));
            setDragStart(point);
        } else if (boxSelection) {
            setBoxSelection(prev => prev ? { ...prev, end: point } : null);
        }
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
            particles.forEach(p => {
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
    };

    const handleClick = (e: React.MouseEvent<SVGElement>) => {
        if (isPanning || boxSelection) return;

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
            timestamp: Date.now()
        };

        onParticlesUpdate([...particles, newParticle]);
    };

    const removeParticleAt = (point: Point) => {
        const clickedParticle = findParticleAt(point);
        if (clickedParticle) {
            onParticlesUpdate(particles.filter(p => p.id !== clickedParticle.id));
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
        return particles.find(p => {
            const dx = p.x - point.x;
            const dy = p.y - point.y;
            return Math.sqrt(dx * dx + dy * dy) <= particleRadius;
        }) || null;
    };

    const getParticleColor = (particle: Point) => {
        const particleClass = particleClasses.find(c => c.id === particle.class);
        const baseColor = particleClass?.color || '#4caf50';

        if (selectedParticles.has(particle.id || '')) {
            return '#2196f3';
        }
        if (hoveredParticle === particle.id) {
            return '#ff9800';
        }

        return baseColor;
    };

    const viewBox = `${-pan.x / zoom} ${-pan.y / zoom} ${width / zoom} ${height / zoom}`;

    return (
        <svg
            ref={svgRef}
            width="100%"
            height="100%"
            viewBox={viewBox}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onClick={handleClick}
            onContextMenu={(e) => e.preventDefault()}
            style={{
                cursor: tool === 'add' ? 'crosshair' :
                    tool === 'move' || tool === 'pan' ? 'move' :
                        tool === 'select' ? 'pointer' :
                            'default',
                backgroundColor: '#000'
            }}
        >
            {/* Grid */}
            {showGrid && (
                <g opacity={0.2}>
                    <defs>
                        <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
                            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="white" strokeWidth="1"/>
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
                {particles.map(particle => {
                    const particleClass = particleClasses.find(c => c.id === particle.class);
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
                            />

                            {showCrosshair && (
                                <>
                                    <line
                                        x1={particle.x - particleRadius/2}
                                        y1={particle.y}
                                        x2={particle.x + particleRadius/2}
                                        y2={particle.y}
                                        stroke={getParticleColor(particle)}
                                        strokeWidth={2}
                                        opacity={particleOpacity}
                                    />
                                    <line
                                        x1={particle.x}
                                        y1={particle.y - particleRadius/2}
                                        x2={particle.x}
                                        y2={particle.y + particleRadius/2}
                                        stroke={getParticleColor(particle)}
                                        strokeWidth={2}
                                        opacity={particleOpacity}
                                    />
                                </>
                            )}

                            {particle.type === 'auto' && particle.confidence && (
                                <circle
                                    cx={particle.x}
                                    cy={particle.y}
                                    r={particleRadius * 0.3}
                                    fill={getParticleColor(particle)}
                                    opacity={particle.confidence}
                                />
                            )}
                        </g>
                    );
                })}
            </g>

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
                />
            )}
        </svg>
    );
};
