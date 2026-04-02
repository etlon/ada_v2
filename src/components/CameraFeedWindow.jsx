import React, { useState, useEffect, useRef } from 'react';
import { X, Camera, Maximize2, Minimize2 } from 'lucide-react';

const CameraFeedWindow = ({ camera, snapshotUrl, annotations = [], onClose }) => {
    const [imgSrc, setImgSrc] = useState(`${snapshotUrl}?t=${Date.now()}`);
    const [isFullscreen, setIsFullscreen] = useState(false);
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

    return (
        <div ref={containerRef} className="w-full h-full relative bg-black/90 rounded-lg overflow-hidden flex flex-col">
            <div data-drag-handle className="h-8 bg-[#222] border-b border-gray-700 flex items-center justify-between px-2 shrink-0 cursor-grab active:cursor-grabbing">
                <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono uppercase tracking-wider">
                    <Camera size={14} />
                    <span>{camera}</span>
                    <span className="text-green-400 text-[10px] animate-pulse">LIVE</span>
                </div>
                <div className="flex items-center gap-1">
                    <button onClick={toggleFullscreen} className="hover:bg-cyan-500/20 text-gray-400 hover:text-cyan-400 p-1 rounded transition-colors">
                        {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                    </button>
                    <button onClick={onClose} className="hover:bg-red-500/20 text-gray-400 hover:text-red-400 p-1 rounded transition-colors">
                        <X size={14} />
                    </button>
                </div>
            </div>
            <div className="flex-1 relative bg-black">
                <img
                    src={imgSrc}
                    alt={camera}
                    className="w-full h-full"
                    style={{ objectFit: 'contain' }}
                />
                {/* Annotation overlay (bounding boxes from Gemini) */}
                {annotations.length > 0 && (
                    <svg
                        className="absolute inset-0 w-full h-full pointer-events-none"
                        viewBox="0 0 1 1"
                        preserveAspectRatio="none"
                    >
                        {annotations.map((ann, i) => {
                            if (ann.type === 'fill') {
                                return (
                                    <rect key={i} x={ann.x} y={ann.y} width={ann.w} height={ann.h} fill={ann.color} opacity={0.3} />
                                );
                            }
                            return (
                                <g key={i}>
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
                )}
            </div>
        </div>
    );
};

export default CameraFeedWindow;
