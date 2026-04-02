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
        <div className="absolute top-20 right-20 z-50 w-[640px] h-[400px] bg-black/90 border border-cyan-500/50 rounded-lg overflow-hidden shadow-[0_0_30px_rgba(6,182,212,0.2)]">
            <div className="h-8 bg-[#222] border-b border-gray-700 flex items-center justify-between px-2">
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
                className="w-full h-[calc(100%-2rem)] object-contain bg-black"
            />
        </div>
    );
};

export default CameraFeedWindow;
