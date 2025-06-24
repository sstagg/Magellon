import React from 'react';
import { ImperativePanelHandle } from 'react-resizable-panels';
import { ChevronLeft, ChevronRight} from '@mui/icons-material';
import { Tooltip, IconButton } from '@mui/material';
import {ChevronDown, ChevronUp} from "lucide-react";

interface PanelCollapseButtonProps {
    panelRef: React.RefObject<ImperativePanelHandle>;
    direction: 'horizontal' | 'vertical';
    position: 'left' | 'right' | 'top' | 'bottom';
    tooltipWhenVisible?: string;
    tooltipWhenCollapsed?: string;
}

const PanelCollapseButton: React.FC<PanelCollapseButtonProps> = ({
                                                                     panelRef,
                                                                     direction,
                                                                     position,
                                                                     tooltipWhenVisible = 'Collapse',
                                                                     tooltipWhenCollapsed = 'Expand'
                                                                 }) => {
    const [isCollapsed, setIsCollapsed] = React.useState(false);

    const togglePanel = () => {
        if (panelRef.current) {
            if (panelRef.current.isCollapsed()) {
                panelRef.current.expand();
                setIsCollapsed(false);
            } else {
                panelRef.current.collapse();
                setIsCollapsed(true);
            }
        }
    };

    // Determine which icon to show based on direction, position, and collapsed state
    const getIcon = () => {
        if (direction === 'horizontal') {
            if (position === 'left') {
                return isCollapsed ? <ChevronRight fontSize="small" /> : <ChevronLeft fontSize="small" />;
            } else {
                return isCollapsed ? <ChevronLeft fontSize="small" /> : <ChevronRight fontSize="small" />;
            }
        } else {
            if (position === 'top') {
                return isCollapsed ? <ChevronDown fontSize="small" /> : <ChevronUp fontSize="small" />;
            } else {
                return isCollapsed ? <ChevronUp fontSize="small" /> : <ChevronDown fontSize="small" />;
            }
        }
    };

    // Calculate positioning styles based on direction and position
    const getPositionStyles = (): React.CSSProperties => {
        if (direction === 'horizontal') {
            // For horizontal resize handle (appears as vertical line)
            return {
                [position]: -12,
                top: '50%',
                transform: 'translateY(-50%)',
                zIndex: 100
            };
        } else {
            // For vertical resize handle (appears as horizontal line)
            return {
                [position]: -12,
                left: '50%',
                transform: 'translateX(-50%)',
                zIndex: 100
            };
        }
    };

    return (
        <Tooltip title={isCollapsed ? tooltipWhenCollapsed : tooltipWhenVisible}>
            <IconButton
                size="small"
                onClick={togglePanel}
                className={`panel-collapse-button panel-collapse-button-${direction}`}
                sx={{
                    position: 'absolute',
                    width: 24,
                    height: 24,
                    backgroundColor: 'background.paper',
                    border: '1px solid',
                    borderColor: 'divider',
                    boxShadow: 1,
                    '&:hover': {
                        backgroundColor: 'action.hover'
                    },
                    ...getPositionStyles()
                }}
            >
                {getIcon()}
            </IconButton>
        </Tooltip>
    );
};

export default PanelCollapseButton;