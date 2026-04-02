import React, { useEffect, useRef, useState } from 'react';
import { renderMasks } from '../segmentation/maskUtils';

const SegmentationOverlay = ({ masks, imgWidth, imgHeight }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const [layout, setLayout] = useState(null);

    // Calculate where the image actually renders within the container (object-fit: contain)
    useEffect(() => {
        const updateLayout = () => {
            const container = containerRef.current?.parentElement;
            if (!container || !imgWidth || !imgHeight) return;

            const cw = container.clientWidth;
            const ch = container.clientHeight;
            const imgAspect = imgWidth / imgHeight;
            const containerAspect = cw / ch;

            let renderW, renderH, offsetX, offsetY;
            if (imgAspect > containerAspect) {
                // Image wider than container — letterbox top/bottom
                renderW = cw;
                renderH = cw / imgAspect;
                offsetX = 0;
                offsetY = (ch - renderH) / 2;
            } else {
                // Image taller than container — letterbox left/right
                renderH = ch;
                renderW = ch * imgAspect;
                offsetX = (cw - renderW) / 2;
                offsetY = 0;
            }

            setLayout({ width: renderW, height: renderH, left: offsetX, top: offsetY });
        };

        updateLayout();
        window.addEventListener('resize', updateLayout);
        return () => window.removeEventListener('resize', updateLayout);
    }, [imgWidth, imgHeight]);

    useEffect(() => {
        if (canvasRef.current && masks && masks.length > 0) {
            renderMasks(canvasRef.current, masks, imgWidth, imgHeight);
        } else if (canvasRef.current) {
            const ctx = canvasRef.current.getContext('2d');
            ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        }
    }, [masks, imgWidth, imgHeight]);

    return (
        <div ref={containerRef} className="absolute inset-0 pointer-events-none z-20">
            {layout && (
                <canvas
                    ref={canvasRef}
                    width={imgWidth}
                    height={imgHeight}
                    style={{
                        position: 'absolute',
                        left: `${layout.left}px`,
                        top: `${layout.top}px`,
                        width: `${layout.width}px`,
                        height: `${layout.height}px`,
                    }}
                />
            )}
        </div>
    );
};

export default SegmentationOverlay;
