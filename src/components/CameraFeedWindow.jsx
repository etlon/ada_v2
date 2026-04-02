import React, { useState, useEffect } from 'react';
import { X, Camera } from 'lucide-react';

const CameraFeedWindow = ({ camera, snapshotUrl, onClose }) => {
    const [imgSrc, setImgSrc] = useState(`${snapshotUrl}?t=${Date.now()}`);

    useEffect(() => {
        const interval = setInterval(() => {
            setImgSrc(`${snapshotUrl}?t=${Date.now()}`);
        }, 1000);
        return () => clearInterval(interval);
    }, [snapshotUrl]);

    return (
        <div className="w-full h-full relative bg-black/90 rounded-lg overflow-hidden flex flex-col">
            <div data-drag-handle className="h-8 bg-[#222] border-b border-gray-700 flex items-center justify-between px-2 shrink-0 cursor-grab active:cursor-grabbing">
                <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono uppercase tracking-wider">
                    <Camera size={14} />
                    <span>{camera}</span>
                    <span className="text-green-400 text-[10px] animate-pulse">LIVE</span>
                </div>
                <button onClick={onClose} className="hover:bg-red-500/20 text-gray-400 hover:text-red-400 p-1 rounded transition-colors">
                    <X size={14} />
                </button>
            </div>
            <img
                src={imgSrc}
                alt={camera}
                className="flex-1 w-full object-contain bg-black"
            />
        </div>
    );
};

export default CameraFeedWindow;
