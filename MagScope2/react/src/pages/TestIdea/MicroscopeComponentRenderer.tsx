import React from 'react';
import { motion } from 'framer-motion';
import type { MicroscopeComponent } from './MicroscopeComponentConfig';
import ElectronParticle from './ElectronParticle';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface MicroscopeComponentRendererProps {
    component: MicroscopeComponent;
    isHovered: boolean;
    isSelected: boolean;
    onHover: () => void;
    onLeave: () => void;
    onSelect: () => void;
    index: number;
}

const MicroscopeComponentRenderer: React.FC<MicroscopeComponentRendererProps> = ({
    component,
    isHovered,
    isSelected,
    onHover,
    onLeave,
    onSelect,
    index
}) => {
    const getShapeStyles = () => {
        const baseWidth = 140;
        const minHeight = 70;
        const maxHeight = 90;

        const heightMap: Record<string, number> = {
            'source': maxHeight,
            'lens': 78,
            'aperture': minHeight,
            'detector': 80,
            'camera': maxHeight,
            'sample': minHeight + 4,
            'electrode': 76,
            'coils': 76
        };

        return {
            width: `${baseWidth}px`,
            height: `${heightMap[component.type] || 78}px`,
            borderRadius: component.shape === 'lens' || component.shape === 'source' ? '50%' : '8px'
        };
    };

    const renderComponentIcon = () => {
        const iconClasses = "w-6 h-6 opacity-70";

        switch (component.shape) {
            case 'source':
                return (
                    <div className={cn(iconClasses, "flex items-center justify-center")}>
                        <div className="w-2 h-2 rounded-full bg-yellow-300 shadow-[0_0_8px_rgba(253,224,71,0.6)]" />
                    </div>
                );
            case 'lens':
                return (
                    <div className={cn(iconClasses, "border-2 border-white/60 rounded-full")} />
                );
            case 'aperture':
                return (
                    <div className={cn(iconClasses, "border-2 border-white/60 rounded flex items-center justify-center")}>
                        <div className="w-1.5 h-1.5 rounded-full bg-black/40" />
                    </div>
                );
            case 'detector':
                return (
                    <div className={cn(iconClasses, "bg-green-500/20 rounded flex items-center justify-center")}>
                        <div className="w-2 h-2 bg-green-500 rounded-full" />
                    </div>
                );
            case 'camera':
                return (
                    <div className={cn(iconClasses, "bg-blue-500/20 rounded flex items-center justify-center")}>
                        <div className="w-3 h-2 border border-blue-500/80 rounded-sm" />
                    </div>
                );
            default:
                return (
                    <div
                        className={cn(iconClasses, "rounded")}
                        style={{ backgroundColor: `${component.baseColor}4D` }}
                    />
                );
        }
    };

    const shapeStyles = getShapeStyles();

    return (
        <>
            <motion.div
                initial={{ opacity: 0, scale: 0.9, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.4, delay: index * 0.08 }}
                whileHover={{ scale: 1.02 }}
                className="mb-2"
                onMouseEnter={onHover}
                onMouseLeave={onLeave}
                onClick={onSelect}
            >
                <div
                    className={cn(
                        "relative cursor-pointer overflow-hidden transition-all duration-200",
                        isSelected && "ring-2 ring-primary shadow-[0_0_12px_rgba(59,130,246,0.4)]",
                        isHovered ? "shadow-2xl" : isSelected ? "shadow-xl" : "shadow-md"
                    )}
                    style={{
                        ...shapeStyles,
                        background: `linear-gradient(135deg, ${component.baseColor}, ${component.baseColor}CC)`,
                        border: isSelected ? '2px solid rgb(59 130 246)' : '1px solid rgba(255, 255, 255, 0.2)'
                    }}
                >
                    {/* Shine effect */}
                    <div
                        className="absolute top-0 left-0 right-0 h-[30%] pointer-events-none"
                        style={{
                            background: 'linear-gradient(to bottom, rgba(255, 255, 255, 0.3), transparent)'
                        }}
                    />

                    {/* Content Container */}
                    <div className="relative h-full flex flex-col items-center justify-center p-2 z-10">
                        {/* Icon */}
                        <div className="mb-1">
                            {renderComponentIcon()}
                        </div>

                        {/* Component Name */}
                        <div className="text-white font-semibold text-center text-shadow-sm mb-0.5 text-sm leading-tight">
                            {component.name}
                        </div>

                        {/* Type Badge */}
                        <Badge
                            className="bg-white/20 text-white text-xs h-5 px-2 hover:bg-white/30"
                        >
                            {component.type}
                        </Badge>

                        {/* Status indicators for specific types */}
                        {(component.type === 'camera' || component.type === 'detector') && (
                            <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" />
                        )}

                        {/* Voltage indicator for source */}
                        {component.type === 'source' && component.specifications?.voltage && (
                            <div className="absolute bottom-1 right-2 text-white/80 text-[0.6rem] font-medium">
                                {component.specifications.voltage}
                            </div>
                        )}
                    </div>

                    {/* Hover overlay */}
                    <div
                        className={cn(
                            "absolute inset-0 bg-primary/10 transition-opacity duration-200",
                            isHovered ? "opacity-100" : "opacity-0"
                        )}
                    />

                    {/* Selection indicator */}
                    {isSelected && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="absolute -inset-0.5 border-2 border-primary rounded-[inherit] shadow-[0_0_12px_rgba(59,130,246,0.4)]"
                            style={{ borderRadius: shapeStyles.borderRadius }}
                        />
                    )}
                </div>
            </motion.div>

            {/* Electron beam visualization */}
            <div className="relative w-0.5 h-6 mx-auto overflow-hidden mt-1">
                {/* Beam path */}
                <div className="absolute left-1/2 -translate-x-1/2 w-px h-full bg-gradient-to-b from-yellow-300/80 via-orange-500/60 to-yellow-300/40" />

                {/* Animated particles */}
                {[...Array(3)].map((_, i) => (
                    <ElectronParticle key={i} delay={i * 0.4} />
                ))}
            </div>
        </>
    );
};

export default MicroscopeComponentRenderer;
