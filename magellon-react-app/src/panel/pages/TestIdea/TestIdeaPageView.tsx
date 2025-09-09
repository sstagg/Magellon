import React, { useState } from 'react';

// Import your existing components (you'll need to adjust these import paths)
import MicroscopeColumn from './MicroscopeColumn';
import PropertyExplorer from './PropertyExplorer';

import {
    ChevronRight
} from 'lucide-react';


export const TestIdeaPageView: React.FC = () => {
    const [isPropertyPanelOpen, setIsPropertyPanelOpen] = useState(true);

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#f3f4f6' }}>
            {/* Header */}
            <div style={{ padding: '16px', paddingBottom: '0px' }}>
                <h1 style={{
                    fontSize: '1.875rem',
                    fontWeight: 'bold',
                    color: '#111827',
                    marginBottom: '8px'
                }}>
                    Microscope Control Interface
                </h1>
                <p style={{ color: '#6b7280' }}>
                    Interactive microscope configuration and property management
                </p>
            </div>

            {/* Main layout container */}
            <div style={{
                display: 'flex',
                flexDirection: 'row',
                width: '100%',
                height: 'calc(100vh - 120px)',
                position: 'relative'
            }}>
                {/* Microscope Column - Left 70% */}
                <div style={{
                    width: '70%',
                    height: '100%',
                    flexShrink: 0
                }}>
                    <MicroscopeColumn />
                </div>

                {/* Property Panel - Right 30% */}
                <div style={{
                    width: isPropertyPanelOpen ? '30%' : '0%',
                    height: '100%',
                    flexShrink: 0,
                    borderLeft: isPropertyPanelOpen ? '1px solid #d1d5db' : 'none',
                    overflow: 'hidden',
                    backgroundColor: '#ffffff',
                    transition: 'width 0.3s ease-in-out'
                }}>
                    {isPropertyPanelOpen && (
                        <div style={{
                            width: '100%',
                            height: '100%',
                            padding: '16px',
                            overflowY: 'auto'
                        }}>
                            <PropertyExplorer />
                        </div>
                    )}
                </div>

                {/* Toggle Button */}
                <button
                    onClick={() => setIsPropertyPanelOpen(!isPropertyPanelOpen)}
                    style={{
                        position: 'absolute',
                        top: '16px',
                        right: isPropertyPanelOpen ? 'calc(30% + 8px)' : '8px',
                        zIndex: 1000,
                        backgroundColor: '#3b82f6',
                        color: '#ffffff',
                        padding: '8px',
                        border: 'none',
                        borderTopLeftRadius: '8px',
                        borderBottomLeftRadius: '8px',
                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                        cursor: 'pointer',
                        transition: 'right 0.3s ease-in-out, background-color 0.2s ease',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}
                    title={isPropertyPanelOpen ? "Hide Properties" : "Show Properties"}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#2563eb';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '#3b82f6';
                    }}
                >
                    <div style={{
                        transform: isPropertyPanelOpen ? 'rotate(0deg)' : 'rotate(180deg)',
                        transition: 'transform 0.3s ease-in-out'
                    }}>
                        <ChevronRight size={20} />
                    </div>
                </button>
            </div>
        </div>
    );
};