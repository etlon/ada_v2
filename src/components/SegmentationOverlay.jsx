import React, { useEffect, useRef, useState, useCallback } from 'react';
import { renderMasks } from '../segmentation/maskUtils';

const SegmentationOverlay = ({ masks, imgWidth, imgHeight }) => {
    const canvasRef = useRef(null);
    const [style, setStyle] = useState({});

    // Calculate position to match object-fit:contain on sibling <img>
    const calcPosition = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const parent = canvas.parentElement;
        if (!parent || !imgWidth || !imgHeight) return;

        const cw = parent.clientWidth;
        const ch = parent.clientHeight;
        const imgRatio = imgWidth / imgHeight;
        const containerRatio = cw / ch;

        let w, h, left, top;
        if (imgRatio > containerRatio) {
            w = cw;
            h = cw / imgRatio;
            left = 0;
            top = (ch - h) / 2;
        } else {
            h = ch;
            w = ch * imgRatio;
            left = (cw - w) / 2;
            top = 0;
        }

        setStyle({
            position: 'absolute',
            left: `${left}px`,
            top: `${top}px`,
            width: `${w}px`,
            height: `${h}px`,
            pointerEvents: 'none',
            zIndex: 20,
        });
    }, [imgWidth, imgHeight]);

    useEffect(() => {
        calcPosition();
        window.addEventListener('resize', calcPosition);
        return () => window.removeEventListener('resize', calcPosition);
    }, [calcPosition]);

    useEffect(() => {
        if (!canvasRef.current) return;
        if (masks && masks.length > 0) {
            renderMasks(canvasRef.current, masks, imgWidth, imgHeight);
            calcPosition();
        } else {
            const ctx = canvasRef.current.getContext('2d');
            ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        }
    }, [masks, imgWidth, imgHeight, calcPosition]);

    return (
        <canvas
            ref={canvasRef}
            width={imgWidth}
            height={imgHeight}
            style={style}
        />
    );
};

export default SegmentationOverlay;
