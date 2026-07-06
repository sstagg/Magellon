import React from 'react';
import { Box, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import { Maximize2, Move, ZoomIn, ZoomOut } from 'lucide-react';

interface ZoomablePreviewProps {
    src: string;
    overlay?: React.ReactNode;
}

const MIN_SCALE = 1;
const MAX_SCALE = 12;

/** Scroll-to-zoom, drag-to-pan wrapper around the test-image preview. */
export const ZoomablePreview: React.FC<ZoomablePreviewProps> = ({ src, overlay }) => {
    const [scale, setScale] = React.useState(1);
    const [offset, setOffset] = React.useState({ x: 0, y: 0 });
    const dragRef = React.useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
    const wrapRef = React.useRef<HTMLDivElement | null>(null);

    const reset = () => { setScale(1); setOffset({ x: 0, y: 0 }); };

    const zoomAroundCenter = (factor: number) => {
        const rect = wrapRef.current?.getBoundingClientRect();
        if (!rect) return;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
        if (nextScale === scale) return;
        const k = nextScale / scale;
        setOffset({
            x: cx - k * (cx - offset.x),
            y: cy - k * (cy - offset.y),
        });
        setScale(nextScale);
    };

    const onWheel = (e: React.WheelEvent) => {
        e.preventDefault();
        const rect = wrapRef.current?.getBoundingClientRect();
        if (!rect) return;
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
        const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale * factor));
        if (nextScale === scale) return;
        const k = nextScale / scale;
        setOffset({
            x: cx - k * (cx - offset.x),
            y: cy - k * (cy - offset.y),
        });
        setScale(nextScale);
    };

    const onMouseDown = (e: React.MouseEvent) => {
        if (scale === 1) return;
        dragRef.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
    };
    const onMouseMove = (e: React.MouseEvent) => {
        if (!dragRef.current) return;
        setOffset({
            x: dragRef.current.ox + (e.clientX - dragRef.current.x),
            y: dragRef.current.oy + (e.clientY - dragRef.current.y),
        });
    };
    const endDrag = () => { dragRef.current = null; };

    return (
        <Box
            ref={wrapRef}
            onWheel={onWheel}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={endDrag}
            onMouseLeave={endDrag}
            onDoubleClick={reset}
            sx={{
                position: 'relative',
                overflow: 'hidden',
                maxWidth: '100%',
                maxHeight: 420,
                cursor: scale > 1 ? (dragRef.current ? 'grabbing' : 'grab') : 'zoom-in',
                userSelect: 'none',
            }}
        >
            <Box
                sx={{
                    transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
                    transformOrigin: '0 0',
                    position: 'relative',
                    display: 'inline-block',
                }}
            >
                <img
                    src={src}
                    alt="Test image preview"
                    draggable={false}
                    style={{ display: 'block', maxWidth: '100%', maxHeight: 420, objectFit: 'contain' }}
                />
                {overlay}
            </Box>
            <Stack
                direction="row"
                spacing={0.5}
                onMouseDown={(e) => e.stopPropagation()}
                onDoubleClick={(e) => e.stopPropagation()}
                sx={{
                    alignItems: "center",
                    position: 'absolute',
                    top: 6,
                    right: 6,
                    bgcolor: 'rgba(0,0,0,0.55)',
                    color: '#fff',
                    px: 0.5,
                    py: 0.25,
                    borderRadius: 1,
                    backdropFilter: 'blur(2px)'
                }}>
                <Tooltip title="Zoom in">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => zoomAroundCenter(1.25)}
                            disabled={scale >= MAX_SCALE}
                            sx={{ color: 'inherit', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
                        >
                            <ZoomIn size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title="Zoom out">
                    <span>
                        <IconButton
                            size="small"
                            onClick={() => zoomAroundCenter(1 / 1.25)}
                            disabled={scale <= MIN_SCALE}
                            sx={{ color: 'inherit', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
                        >
                            <ZoomOut size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title="Reset (double-click image)">
                    <span>
                        <IconButton
                            size="small"
                            onClick={reset}
                            disabled={scale === 1 && offset.x === 0 && offset.y === 0}
                            sx={{ color: 'inherit', '&.Mui-disabled': { color: 'rgba(255,255,255,0.35)' } }}
                        >
                            <Maximize2 size={16} />
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title={scale > 1 ? 'Drag the image to pan' : 'Zoom in to pan'}>
                    <Box sx={{ display: 'flex', alignItems: 'center', px: 0.25, opacity: scale > 1 ? 1 : 0.45 }}>
                        <Move size={14} />
                    </Box>
                </Tooltip>
                <Typography variant="caption" sx={{ minWidth: 38, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {Math.round(scale * 100)}%
                </Typography>
            </Stack>
        </Box>
    );
};
