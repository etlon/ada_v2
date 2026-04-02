import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { X, Camera, Maximize2, Minimize2, ZoomOut, ZoomIn } from 'lucide-react';

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

const MIN_SCALE = 1;
const MAX_SCALE = 10;
const SCROLL_FACTOR = 1.15;

const CameraFeedWindow = ({ camera, snapshotUrl, annotations = [], trackedObjects = [], zoomTarget, onZoomReset, onClose }) => {
    const [imgSrc, setImgSrc] = useState(`${snapshotUrl}?t=${Date.now()}`);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [showTracking, setShowTracking] = useState(true);
    const containerRef = useRef(null);
    const viewportRef = useRef(null);

    // Pan-zoom state: scale + translate (in pixels relative to the viewport)
    const [scale, setScale] = useState(1);
    const [translate, setTranslate] = useState({ x: 0, y: 0 });
    const isPanningRef = useRef(false);
    const panStartRef = useRef({ x: 0, y: 0 });
    const translateStartRef = useRef({ x: 0, y: 0 });

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

    // Combine all labeled items for zoom lookup
    const allLabeled = useMemo(() => {
        const items = [...annotations];
        trackedObjects.forEach(obj => {
            items.push({ x: obj.x, y: obj.y, w: obj.w, h: obj.h, label: obj.label });
        });
        return items;
    }, [annotations, trackedObjects]);

    // When zoomTarget changes (Gemini says "zoom into X"), compute initial pan-zoom
    useEffect(() => {
        if (!zoomTarget || !zoomTarget.label || allLabeled.length === 0) return;
        const targetLabel = zoomTarget.label.toLowerCase();
        const match = allLabeled.find(a => a.label && a.label.toLowerCase().includes(targetLabel))
            || allLabeled.find(a => a.label && targetLabel.includes(a.label.toLowerCase()));
        if (!match || !viewportRef.current) return;

        const pad = 0.15;
        const rx = Math.max(0, match.x - match.w * pad);
        const ry = Math.max(0, match.y - match.h * pad);
        const rw = Math.min(1 - rx, match.w * (1 + 2 * pad));
        const rh = Math.min(1 - ry, match.h * (1 + 2 * pad));

        const rect = viewportRef.current.getBoundingClientRect();
        const scaleX = rect.width / (rw * rect.width);
        const scaleY = rect.height / (rh * rect.height);
        const newScale = Math.min(Math.max(Math.min(scaleX, scaleY), MIN_SCALE), MAX_SCALE);

        // Center the region
        const centerX = (rx + rw / 2) * rect.width;
        const centerY = (ry + rh / 2) * rect.height;
        const newTx = rect.width / 2 - centerX * newScale;
        const newTy = rect.height / 2 - centerY * newScale;

        setScale(newScale);
        setTranslate(clampTranslate(newTx, newTy, newScale, rect.width, rect.height));
    }, [zoomTarget, allLabeled]);

    // Clamp translate so we don't pan outside the image
    const clampTranslate = useCallback((tx, ty, s, vw, vh) => {
        const minX = vw - vw * s;
        const minY = vh - vh * s;
        return {
            x: Math.min(0, Math.max(minX, tx)),
            y: Math.min(0, Math.max(minY, ty)),
        };
    }, []);

    // Mouse wheel zoom (zoom towards cursor position)
    const handleWheel = useCallback((e) => {
        e.preventDefault();
        const rect = viewportRef.current?.getBoundingClientRect();
        if (!rect) return;

        const cursorX = e.clientX - rect.left;
        const cursorY = e.clientY - rect.top;

        setScale(prevScale => {
            const direction = e.deltaY < 0 ? SCROLL_FACTOR : 1 / SCROLL_FACTOR;
            const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prevScale * direction));
            const ratio = newScale / prevScale;

            setTranslate(prev => {
                const newTx = cursorX - (cursorX - prev.x) * ratio;
                const newTy = cursorY - (cursorY - prev.y) * ratio;
                return clampTranslate(newTx, newTy, newScale, rect.width, rect.height);
            });

            return newScale;
        });
    }, [clampTranslate]);

    // Attach wheel listener with passive: false
    useEffect(() => {
        const el = viewportRef.current;
        if (!el) return;
        el.addEventListener('wheel', handleWheel, { passive: false });
        return () => el.removeEventListener('wheel', handleWheel);
    }, [handleWheel]);

    // Mouse drag to pan
    const handleMouseDown = useCallback((e) => {
        if (scale <= 1) return;
        e.preventDefault();
        isPanningRef.current = true;
        panStartRef.current = { x: e.clientX, y: e.clientY };
        translateStartRef.current = { ...translate };
    }, [scale, translate]);

    const handleMouseMove = useCallback((e) => {
        if (!isPanningRef.current) return;
        const rect = viewportRef.current?.getBoundingClientRect();
        if (!rect) return;
        const dx = e.clientX - panStartRef.current.x;
        const dy = e.clientY - panStartRef.current.y;
        const newTx = translateStartRef.current.x + dx;
        const newTy = translateStartRef.current.y + dy;
        setTranslate(clampTranslate(newTx, newTy, scale, rect.width, rect.height));
    }, [scale, clampTranslate]);

    const handleMouseUp = useCallback(() => {
        isPanningRef.current = false;
    }, []);

    useEffect(() => {
        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [handleMouseMove, handleMouseUp]);

    // Reset zoom
    const resetZoom = useCallback(() => {
        setScale(1);
        setTranslate({ x: 0, y: 0 });
        onZoomReset?.();
    }, [onZoomReset]);

    const isZoomed = scale > 1.01;
    const hasTracking = trackedObjects.length > 0;
    const zoomLabel = zoomTarget?.label;

    const transformStyle = {
        transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
        transformOrigin: '0 0',
        transition: isPanningRef.current ? 'none' : 'transform 0.3s ease',
    };

    return (
        <div ref={containerRef} className="w-full h-full relative bg-black/90 rounded-lg overflow-hidden flex flex-col">
            {/* Title bar */}
            <div data-drag-handle className="h-8 bg-[#222] border-b border-gray-700 flex items-center justify-between px-2 shrink-0 cursor-grab active:cursor-grabbing">
                <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono uppercase tracking-wider">
                    <Camera size={14} />
                    <span>{camera}</span>
                    {isZoomed && zoomLabel && (
                        <span className="text-yellow-400 text-[10px]">ZOOM: {zoomLabel}</span>
                    )}
                    {isZoomed && !zoomLabel && (
                        <span className="text-yellow-400 text-[10px]">{Math.round(scale * 100)}%</span>
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
                            onClick={resetZoom}
                            className="hover:bg-yellow-500/20 text-yellow-400 hover:text-yellow-300 p-1 rounded transition-colors"
                            title="Reset zoom (1x)"
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
            <div
                ref={viewportRef}
                className="flex-1 relative bg-black overflow-hidden"
                style={{ cursor: isZoomed ? 'grab' : 'default' }}
                onMouseDown={handleMouseDown}
            >
                <div className="w-full h-full" style={transformStyle}>
                    <img
                        src={imgSrc}
                        alt={camera}
                        className="w-full h-full"
                        style={{ objectFit: 'contain' }}
                        draggable={false}
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
                                    <rect
                                        x={obj.x} y={obj.y} width={obj.w} height={obj.h}
                                        fill="none" stroke={color} strokeWidth={0.002}
                                        strokeDasharray="0.008 0.004"
                                    />
                                    <CornerAccents x={obj.x} y={obj.y} w={obj.w} h={obj.h} color={color} />
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

                {/* Zoom level indicator (bottom-left) */}
                {isZoomed && (
                    <div className="absolute bottom-2 left-2 bg-black/70 text-yellow-400 text-[10px] font-mono px-2 py-1 rounded pointer-events-none">
                        <ZoomIn size={10} className="inline mr-1" />
                        {scale.toFixed(1)}x — scroll to zoom, drag to pan
                    </div>
                )}
            </div>
        </div>
    );
};

// Corner accent lines for tracked object boxes
const CornerAccents = ({ x, y, w, h, color }) => {
    const len = 0.015;
    const sw = 0.004;
    return (
        <>
            <line x1={x} y1={y} x2={x + len} y2={y} stroke={color} strokeWidth={sw} />
            <line x1={x} y1={y} x2={x} y2={y + len} stroke={color} strokeWidth={sw} />
            <line x1={x + w} y1={y} x2={x + w - len} y2={y} stroke={color} strokeWidth={sw} />
            <line x1={x + w} y1={y} x2={x + w} y2={y + len} stroke={color} strokeWidth={sw} />
            <line x1={x} y1={y + h} x2={x + len} y2={y + h} stroke={color} strokeWidth={sw} />
            <line x1={x} y1={y + h} x2={x} y2={y + h - len} stroke={color} strokeWidth={sw} />
            <line x1={x + w} y1={y + h} x2={x + w - len} y2={y + h} stroke={color} strokeWidth={sw} />
            <line x1={x + w} y1={y + h} x2={x + w} y2={y + h - len} stroke={color} strokeWidth={sw} />
        </>
    );
};

export default CameraFeedWindow;
