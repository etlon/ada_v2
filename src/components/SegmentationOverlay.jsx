import React, { useEffect, useRef } from 'react';
import { renderMasks } from '../segmentation/maskUtils';

const SegmentationOverlay = ({ masks, imgWidth, imgHeight }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
        if (canvasRef.current && masks && masks.length > 0) {
            renderMasks(canvasRef.current, masks, imgWidth, imgHeight);
        } else if (canvasRef.current) {
            const ctx = canvasRef.current.getContext('2d');
            ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        }
    }, [masks, imgWidth, imgHeight]);

    // Match the image's object-fit: contain behavior by using the same
    // intrinsic dimensions. The CSS object-fit: contain on the canvas
    // will then align it identically to the <img> element.
    return (
        <canvas
            ref={canvasRef}
            width={imgWidth}
            height={imgHeight}
            className="absolute inset-0 w-full h-full pointer-events-none z-20"
            style={{ objectFit: 'contain' }}
        />
    );
};

export default SegmentationOverlay;
