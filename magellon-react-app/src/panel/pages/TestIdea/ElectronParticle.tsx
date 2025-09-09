import React from 'react';
import { motion } from 'framer-motion';

interface ElectronParticleProps {
    delay: number;
}

const ElectronParticle: React.FC<ElectronParticleProps> = ({ delay }) => (
    <motion.div
        style={{
            position: 'absolute',
            width: 2,
            height: 2,
            backgroundColor: '#FDE047',
            borderRadius: '50%',
            opacity: 0.6
        }}
        initial={{ y: -10, opacity: 0 }}
        animate={{
            y: 20,
            opacity: [0, 0.8, 0.8, 0],
            scale: [0.5, 1, 1, 0.5]
        }}
        transition={{
            duration: 1.2,
            delay,
            repeat: Infinity,
            ease: "linear"
        }}
    />
);

export default ElectronParticle;