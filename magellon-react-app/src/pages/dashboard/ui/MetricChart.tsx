import { Box, alpha } from "@mui/material";
import type { MetricChartProps } from '../model/types.ts';

// Custom chart component for the metrics card
export const MetricChart = ({ data, color, height = 40 }: MetricChartProps) => {
    const maxValue = Math.max(...data);

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'flex-end',
            height,
            gap: 0.5,
            mt: 1
        }}>
            {data.map((value, index) => (
                <Box
                    key={index}
                    sx={{
                        height: `${(value / maxValue) * 100}%`,
                        width: '4px',
                        backgroundColor: alpha(color, 0.7),
                        borderRadius: '2px',
                        transition: 'height 0.3s ease',
                        '&:hover': {
                            backgroundColor: color,
                            transform: 'scaleY(1.1)',
                        }
                    }}
                />
            ))}
        </Box>
    );
};
