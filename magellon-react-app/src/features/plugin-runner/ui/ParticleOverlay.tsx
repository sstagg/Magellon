import React from 'react';
import type { PreviewResult } from '../model/previewTypes.ts';

interface ParticleOverlayProps {
    result: PreviewResult | Record<string, unknown> | null;
    diameterAngstrom?: number;
    imagePixelSize?: number;
}

/** SVG circle overlay drawing picked particles on top of the preview image. */
export const ParticleOverlay: React.FC<ParticleOverlayProps> = ({ result, diameterAngstrom, imagePixelSize }) => {
    if (!result) return null;
    const particles = Array.isArray(result.particles) ? result.particles : [];
    const shape = result.image_shape as [number, number] | undefined;
    if (!particles.length || !shape || shape.length !== 2) return null;
    const [h, w] = shape;

    // Particle radius in binned-image pixels; fall back to 1.2% of image width.
    const bin = Number(result.image_binning) || 1;
    const targetApix = Number(result.target_pixel_size) || (imagePixelSize ? imagePixelSize * bin : undefined);
    const radiusBinned =
        diameterAngstrom && targetApix ? diameterAngstrom / targetApix / 2 : w * 0.012;

    return (
        <svg
            viewBox={`0 0 ${w} ${h}`}
            preserveAspectRatio="xMidYMid meet"
            style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
            }}
        >
            {particles.map((p: { x: number; y: number }, i: number) => (
                <circle
                    key={i}
                    cx={p.x}
                    cy={p.y}
                    r={radiusBinned}
                    fill="none"
                    stroke="#00e676"
                    strokeWidth={Math.max(w, h) * 0.002}
                    opacity={0.9}
                />
            ))}
        </svg>
    );
};
