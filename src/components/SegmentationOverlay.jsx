import React, { useEffect, useRef } from 'react';
import { renderMasks } from '../segmentation/maskUtils';

const SegmentationOverlay = ({ masks, imgWidth, imgHeight, objectFit = 'cover' }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
        if (!canvasRef.current) return;
        if (masks && masks.length > 0) {
            renderMasks(canvasRef.current, masks, imgWidth, imgHeight);
        } else {
            const ctx = canvasRef.current.getContext('2d');
            ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        }
    }, [masks, imgWidth, imgHeight]);

    return (
        <canvas
            ref={canvasRef}
            width={imgWidth}
            height={imgHeight}
            className="absolute inset-0 w-full h-full pointer-events-none z-20"
            style={{ objectFit }}
        />
    );
};

export default SegmentationOverlay;
