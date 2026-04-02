import React, { useEffect, useState } from 'react';

const SegmentationOverlay = ({ masks, imgWidth, imgHeight, objectFit = 'contain' }) => {
    const [dataUrl, setDataUrl] = useState(null);

    useEffect(() => {
        if (!masks || masks.length === 0 || !imgWidth || !imgHeight) {
            setDataUrl(null);
            return;
        }

        // Render masks to an offscreen canvas and export as data URL
        const canvas = document.createElement('canvas');
        canvas.width = imgWidth;
        canvas.height = imgHeight;
        const ctx = canvas.getContext('2d');

        for (const { mask, color } of masks) {
            const maskData = mask.data;
            const [h, w] = mask.dims;
            const rgba = parseColor(color);

            const imageData = ctx.createImageData(w, h);
            for (let i = 0; i < maskData.length; i++) {
                if (maskData[i]) {
                    imageData.data[i * 4] = rgba[0];
                    imageData.data[i * 4 + 1] = rgba[1];
                    imageData.data[i * 4 + 2] = rgba[2];
                    imageData.data[i * 4 + 3] = rgba[3];
                }
            }

            // Draw at mask resolution then scale
            const tmp = document.createElement('canvas');
            tmp.width = w;
            tmp.height = h;
            tmp.getContext('2d').putImageData(imageData, 0, 0);
            ctx.drawImage(tmp, 0, 0, imgWidth, imgHeight);
        }

        setDataUrl(canvas.toDataURL('image/png'));
    }, [masks, imgWidth, imgHeight]);

    if (!dataUrl) return null;

    // Use an <img> with the SAME object-fit as the camera image
    // This guarantees identical positioning/letterboxing
    return (
        <img
            src={dataUrl}
            className="absolute inset-0 w-full h-full pointer-events-none z-20"
            style={{ objectFit }}
            alt=""
        />
    );
};

function parseColor(color) {
    const rgbaMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (rgbaMatch) {
        return [
            parseInt(rgbaMatch[1]),
            parseInt(rgbaMatch[2]),
            parseInt(rgbaMatch[3]),
            Math.round(parseFloat(rgbaMatch[4] ?? 1) * 255),
        ];
    }
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.fillStyle = color;
    const hex = ctx.fillStyle;
    return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16), 102];
}

export default SegmentationOverlay;
