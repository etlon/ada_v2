import React, { useState, useEffect, useRef, useMemo } from 'react';
import { X, Camera, Maximize2, Minimize2, ZoomOut } from 'lucide-react';

// Color map for Frigate object types
const OBJECT_COLORS = {
    person: '#ef4444',   // red
    car: '#3b82f6',      // blue
    truck: '#8b5cf6',    // purple
    motorcycle: '#f97316', // orange
    bicycle: '#eab308',  // yellow
    dog: '#22c55e',      // green
    cat: '#a855f7',      // violet
    bird: '#06b6d4',     // cyan
};

const getObjectColor = (label) => OBJECT_COLORS[label] || '#06b6d4';

const CameraFeedWindow = ({ camera, snapshotUrl, annotations = [], trackedObjects = [], zoomTarget, onZoomReset, onClose }) => {
    const [imgSrc, setImgSrc] = useState(`${snapshotUrl}?t=${Date.now()}`);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [showTracking, setShowTracking] = useState(true);
    const containerRef = useRef(null);

    useEffect(() => {
        const interval = setInterval(() => {
            setImgSrc(`${snapshotUrl}?t=${Date.now()}`);
        }, 1000);
        return () => clearInterval(interval);
    }, [snapshotUrl]);

    const toggleFullscreen = () => {
        if (!isFullscreen) {
            containerRef.current?.requestFullscreen?.();
        } else {
            document.exitFullscreen?.();
        }
    };

    useEffect(() => {
        const handler = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener('fullscreenchange', handler);
        return () => document.removeEventListener('fullscreenchange', handler);
    }, []);

    // Combine all labeled items (annotations + tracked objects) for zoom lookup
    const allLabeled = useMemo(() => {
        const items = [...annotations];
        trackedObjects.forEach(obj => {
            items.push({ x: obj.x, y: obj.y, w: obj.w, h: obj.h, label: obj.label });
        });
        return items;
    }, [annotations, trackedObjects]);

    // Find the matching region for zoom
    const zoomRegion = useMemo(() => {
        if (!zoomTarget || !zoomTarget.label || allLabeled.length === 0) return null;
        const targetLabel = zoomTarget.label.toLowerCase();
        const match = allLabeled.find(a => a.label && a.label.toLowerCase().includes(targetLabel))
            || allLabeled.find(a => a.label && targetLabel.includes(a.label.toLowerCase()));
        if (!match) return null;
        const pad = 0.15;
        const x = Math.max(0, match.x - match.w * pad);
        const y = Math.max(0, match.y - match.h * pad);
        const w = Math.min(1 - x, match.w * (1 + 2 * pad));
        const h = Math.min(1 - y, match.h * (1 + 2 * pad));
        return { x, y, w, h, label: match.label };
    }, [zoomTarget, allLabeled]);

    // CSS transform for zoom
    const zoomStyle = useMemo(() => {
        if (!zoomRegion) return {};
        const scaleX = 1 / zoomRegion.w;
        const scaleY = 1 / zoomRegion.h;
        const scale = Math.min(scaleX, scaleY);
        const originX = (zoomRegion.x + zoomRegion.w / 2) * 100;
        const originY = (zoomRegion.y + zoomRegion.h / 2) * 100;
        return {
            transform: `scale(${scale})`,
            transformOrigin: `${originX}% ${originY}%`,
            transition: 'transform 0.5s ease, transform-origin 0.5s ease',
        };
    }, [zoomRegion]);

    const isZoomed = !!zoomRegion;
    const hasTracking = trackedObjects.length > 0;

    return (
        <div ref={containerRef} className="w-full h-full relative bg-black/90 rounded-lg overflow-hidden flex flex-col">
            {/* Title bar */}
            <div data-drag-handle className="h-8 bg-[#222] border-b border-gray-700 flex items-center justify-between px-2 shrink-0 cursor-grab active:cursor-grabbing">
                <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono uppercase tracking-wider">
                    <Camera size={14} />
                    <span>{camera}</span>
                    {isZoomed && (
                        <span className="text-yellow-400 text-[10px]">ZOOM: {zoomRegion.label}</span>
                    )}
                    {!isZoomed && (
                        <span className="text-green-400 text-[10px] animate-pulse">LIVE</span>
                    )}
                    {hasTracking && showTracking && (
                        <span className="text-orange-400 text-[10px]">
                            {trackedObjects.length} TRACKED
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    {hasTracking && (
                        <button
                            onClick={() => setShowTracking(!showTracking)}
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded transition-colors ${
                                showTracking
                                    ? 'bg-orange-500/20 text-orange-400'
                                    : 'bg-gray-700/50 text-gray-500'
                            }`}
                            title={showTracking ? 'Hide tracking' : 'Show tracking'}
                        >
                            TRK
                        </button>
                    )}
                    {isZoomed && (
                        <button
                            onClick={onZoomReset}
                            className="hover:bg-yellow-500/20 text-yellow-400 hover:text-yellow-300 p-1 rounded transition-colors"
                            title="Reset zoom"
                        >
                            <ZoomOut size={14} />
                        </button>
                    )}
                    <button onClick={toggleFullscreen} className="hover:bg-cyan-500/20 text-gray-400 hover:text-cyan-400 p-1 rounded transition-colors">
                        {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                    </button>
                    <button onClick={onClose} className="hover:bg-red-500/20 text-gray-400 hover:text-red-400 p-1 rounded transition-colors">
                        <X size={14} />
                    </button>
                </div>
            </div>

            {/* Camera image + overlays */}
            <div className="flex-1 relative bg-black overflow-hidden">
                <div className="w-full h-full" style={zoomStyle}>
                    <img
                        src={imgSrc}
                        alt={camera}
                        className="w-full h-full"
                        style={{ objectFit: 'contain' }}
                    />
                    <svg
                        className="absolute inset-0 w-full h-full pointer-events-none"
                        viewBox="0 0 1 1"
                        preserveAspectRatio="none"
                    >
                        {/* Frigate live tracked objects */}
                        {showTracking && trackedObjects.map((obj) => {
                            const color = getObjectColor(obj.label);
                            return (
                                <g key={obj.id}>
                                    {/* Dashed bounding box */}
                                    <rect
                                        x={obj.x} y={obj.y} width={obj.w} height={obj.h}
                                        fill="none" stroke={color} strokeWidth={0.002}
                                        strokeDasharray="0.008 0.004"
                                    />
                                    {/* Corner accents */}
                                    <CornerAccents x={obj.x} y={obj.y} w={obj.w} h={obj.h} color={color} />
                                    {/* Label + score */}
                                    <rect
                                        x={obj.x} y={Math.max(0, obj.y - 0.028)}
                                        width={Math.min((obj.label.length + 4) * 0.01 + 0.01, 0.3)} height={0.026}
                                        fill={color} opacity={0.85} rx={0.003}
                                    />
                                    <text
                                        x={obj.x + 0.005} y={Math.max(0.018, obj.y - 0.008)}
                                        fill="white" fontSize={0.016} fontFamily="monospace" fontWeight="bold"
                                    >
                                        {obj.label} {Math.round(obj.score * 100)}%
                                    </text>
                                </g>
                            );
                        })}

                        {/* Gemini annotations (user-requested) */}
                        {annotations.map((ann, i) => {
                            if (ann.type === 'fill') {
                                return (
                                    <rect key={`ann-${i}`} x={ann.x} y={ann.y} width={ann.w} height={ann.h} fill={ann.color} opacity={0.3} />
                                );
                            }
                            return (
                                <g key={`ann-${i}`}>
                                    <rect x={ann.x} y={ann.y} width={ann.w} height={ann.h} fill="none" stroke={ann.color} strokeWidth={0.003} />
                                    {ann.label && (
                                        <g>
                                            <rect x={ann.x} y={Math.max(0, ann.y - 0.03)} width={Math.min(ann.label.length * 0.012 + 0.01, 0.3)} height={0.028} fill={ann.color} opacity={0.8} />
                                            <text x={ann.x + 0.005} y={Math.max(0.02, ann.y - 0.008)} fill="white" fontSize={0.018} fontFamily="monospace" fontWeight="bold">{ann.label}</text>
                                        </g>
                                    )}
                                </g>
                            );
                        })}
                    </svg>
                </div>
            </div>
        </div>
    );
};

// Corner accent lines for tracked object boxes
const CornerAccents = ({ x, y, w, h, color }) => {
    const len = 0.015; // accent line length
    const sw = 0.004;  // stroke width
    return (
        <>
            {/* Top-left */}
            <line x1={x} y1={y} x2={x + len} y2={y} stroke={color} strokeWidth={sw} />
            <line x1={x} y1={y} x2={x} y2={y + len} stroke={color} strokeWidth={sw} />
            {/* Top-right */}
            <line x1={x + w} y1={y} x2={x + w - len} y2={y} stroke={color} strokeWidth={sw} />
            <line x1={x + w} y1={y} x2={x + w} y2={y + len} stroke={color} strokeWidth={sw} />
            {/* Bottom-left */}
            <line x1={x} y1={y + h} x2={x + len} y2={y + h} stroke={color} strokeWidth={sw} />
            <line x1={x} y1={y + h} x2={x} y2={y + h - len} stroke={color} strokeWidth={sw} />
            {/* Bottom-right */}
            <line x1={x + w} y1={y + h} x2={x + w - len} y2={y + h} stroke={color} strokeWidth={sw} />
            <line x1={x + w} y1={y + h} x2={x + w} y2={y + h - len} stroke={color} strokeWidth={sw} />
        </>
    );
};

export default CameraFeedWindow;
