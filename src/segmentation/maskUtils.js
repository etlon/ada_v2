// Reusable canvases to avoid repeated allocation
let _colorParseCtx = null;
let _tempCanvas = null;

/**
 * Renders SAM mask tensors onto a canvas as colored overlays.
 * @param {HTMLCanvasElement} canvas - Target canvas
 * @param {Array} masks - Array of { mask (Tensor [H,W]), color (CSS color string) }
 * @param {number} imgWidth - Original image width
 * @param {number} imgHeight - Original image height
 */
export function renderMasks(canvas, masks, imgWidth, imgHeight) {
    canvas.width = imgWidth;
    canvas.height = imgHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, imgWidth, imgHeight);

    for (const { mask, color } of masks) {
        const maskData = mask.data;
        const [h, w] = mask.dims.slice(-2);

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

        // Reuse a single temp canvas
        if (!_tempCanvas) _tempCanvas = document.createElement('canvas');
        _tempCanvas.width = w;
        _tempCanvas.height = h;
        _tempCanvas.getContext('2d').putImageData(imageData, 0, 0);

        ctx.drawImage(_tempCanvas, 0, 0, imgWidth, imgHeight);
    }
}

function parseColor(color) {
    const rgbaMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (rgbaMatch) {
        return [
            parseInt(rgbaMatch[1]),
            parseInt(rgbaMatch[2]),
            parseInt(rgbaMatch[3]),
            Math.round((parseFloat(rgbaMatch[4] ?? 1) * 255)),
        ];
    }

    // Reuse a single canvas context for color parsing
    if (!_colorParseCtx) _colorParseCtx = document.createElement('canvas').getContext('2d');
    _colorParseCtx.fillStyle = color;
    const hex = _colorParseCtx.fillStyle;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return [r, g, b, 102]; // ~40% opacity
}
