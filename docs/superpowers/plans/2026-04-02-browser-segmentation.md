# Browser-Based Semantic Segmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable pixel-accurate semantic segmentation on camera feeds via voice commands (e.g., "Markiere die Straße"), running entirely in the browser on the user's GPU via WebGPU.

**Architecture:** Grounding DINO converts text prompts to bounding boxes, then SlimSAM generates pixel-accurate masks from those boxes. Both models run client-side via Transformers.js with WebGPU backend. Gemini handles intent parsing and calls a `segment_camera` tool, which sends the target label to the frontend. The frontend runs the ML pipeline and renders the mask as a canvas overlay.

**Tech Stack:** @huggingface/transformers (v3.8+), Grounding DINO (onnx-community/grounding-dino-tiny-ONNX), SlimSAM (Xenova/slimsam-77-uniform), WebGPU, Canvas API

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/segmentation/SegmentationEngine.js` (create) | Loads Grounding DINO + SlimSAM models, runs inference, returns mask data |
| `src/segmentation/maskUtils.js` (create) | Converts SAM mask tensors to canvas-renderable ImageData with colors |
| `src/components/CameraFeedWindow.jsx` (modify) | Renders mask overlay canvas on top of camera snapshot |
| `src/components/SegmentationOverlay.jsx` (create) | Canvas component that draws colored mask overlays |
| `src/App.jsx` (modify) | Handles `segment_camera` socket event, passes to SegmentationEngine, manages mask state |
| `backend/ada.py` (modify) | Adds `segment_camera` tool definition + dispatch (sends label to frontend, replaces `annotate_camera` for segmentation use cases) |
| `backend/server.py` (modify) | Adds socket event to forward segmentation request to frontend |

---

### Task 1: Install Transformers.js dependency

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Install @huggingface/transformers**

```bash
npm install @huggingface/transformers
```

- [ ] **Step 2: Verify installation**

```bash
node -e "const t = require('@huggingface/transformers'); console.log('OK:', Object.keys(t).length, 'exports')"
```

Expected: `OK: <number> exports`

- [ ] **Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "chore: add @huggingface/transformers for browser ML"
```

---

### Task 2: Create SegmentationEngine

**Files:**
- Create: `src/segmentation/SegmentationEngine.js`

- [ ] **Step 1: Create the engine module**

```javascript
import { pipeline, SamModel, AutoProcessor, RawImage } from '@huggingface/transformers';

const GROUNDING_DINO_MODEL = 'onnx-community/grounding-dino-tiny-ONNX';
const SAM_MODEL = 'Xenova/slimsam-77-uniform';

class SegmentationEngine {
    constructor() {
        this.detector = null;
        this.samModel = null;
        this.samProcessor = null;
        this.loading = false;
        this.ready = false;
        this.onProgress = null; // callback({ model, progress })
    }

    async load(onProgress) {
        if (this.ready || this.loading) return;
        this.loading = true;
        this.onProgress = onProgress || null;

        try {
            // Load Grounding DINO for text-to-box detection
            if (this.onProgress) this.onProgress({ model: 'Grounding DINO', progress: 0 });
            this.detector = await pipeline('zero-shot-object-detection', GROUNDING_DINO_MODEL, {
                device: 'webgpu',
                dtype: 'fp32',
            });
            if (this.onProgress) this.onProgress({ model: 'Grounding DINO', progress: 100 });

            // Load SlimSAM for segmentation
            if (this.onProgress) this.onProgress({ model: 'SlimSAM', progress: 0 });
            this.samModel = await SamModel.from_pretrained(SAM_MODEL, {
                device: 'webgpu',
                dtype: {
                    vision_encoder: 'fp16',
                    prompt_encoder_mask_decoder: 'fp16',
                },
            });
            this.samProcessor = await AutoProcessor.from_pretrained(SAM_MODEL);
            if (this.onProgress) this.onProgress({ model: 'SlimSAM', progress: 100 });

            this.ready = true;
        } catch (e) {
            console.error('[SegmentationEngine] Failed to load models:', e);
            throw e;
        } finally {
            this.loading = false;
        }
    }

    async segment(imageUrl, textPrompt, options = {}) {
        if (!this.ready) throw new Error('Models not loaded. Call load() first.');

        const { threshold = 0.3, color = 'rgba(255, 255, 0, 0.4)' } = options;

        // Step 1: Grounding DINO — text to bounding boxes
        const labels = textPrompt.toLowerCase().endsWith('.')
            ? [textPrompt.toLowerCase()]
            : [textPrompt.toLowerCase() + '.'];

        const detections = await this.detector(imageUrl, labels, { threshold });

        if (!detections || detections.length === 0) {
            return { masks: [], message: `Nothing matching "${textPrompt}" found.` };
        }

        // Step 2: SAM — bounding boxes to pixel masks
        const rawImage = await RawImage.read(imageUrl);
        const results = [];

        for (const det of detections) {
            const { xmin, ymin, xmax, ymax } = det.box;
            const input_boxes = [[[xmin, ymin, xmax, ymax]]];

            const inputs = await this.samProcessor(rawImage, { input_boxes });
            const outputs = await this.samModel(inputs);

            const masks = await this.samProcessor.post_process_masks(
                outputs.pred_masks,
                inputs.original_sizes,
                inputs.reshaped_input_sizes
            );

            // masks[0][0] is a Tensor of shape [H, W] with boolean values
            // Get the highest-scoring mask
            const scores = outputs.iou_scores.data;
            let bestIdx = 0;
            for (let i = 1; i < scores.length; i++) {
                if (scores[i] > scores[bestIdx]) bestIdx = i;
            }

            results.push({
                label: det.label,
                score: det.score,
                box: det.box,
                mask: masks[0][bestIdx], // Tensor [H, W]
                color,
            });
        }

        return { masks: results, width: rawImage.width, height: rawImage.height };
    }
}

// Singleton
const engine = new SegmentationEngine();
export default engine;
```

- [ ] **Step 2: Commit**

```bash
git add src/segmentation/SegmentationEngine.js
git commit -m "feat: add SegmentationEngine with Grounding DINO + SlimSAM"
```

---

### Task 3: Create mask rendering utilities

**Files:**
- Create: `src/segmentation/maskUtils.js`

- [ ] **Step 1: Create mask-to-canvas utility**

```javascript
/**
 * Renders a SAM mask tensor onto a canvas as a colored overlay.
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

        // Parse color to RGBA
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

        // Draw to temp canvas at mask resolution, then scale to target
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        tempCanvas.getContext('2d').putImageData(imageData, 0, 0);

        ctx.drawImage(tempCanvas, 0, 0, imgWidth, imgHeight);
    }
}

function parseColor(color) {
    // Handle rgba(r, g, b, a) format
    const rgbaMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (rgbaMatch) {
        return [
            parseInt(rgbaMatch[1]),
            parseInt(rgbaMatch[2]),
            parseInt(rgbaMatch[3]),
            Math.round((parseFloat(rgbaMatch[4] ?? 1) * 255)),
        ];
    }

    // Named colors -> lookup via temporary canvas
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.fillStyle = color;
    const hex = ctx.fillStyle; // Browser normalizes to #rrggbb
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return [r, g, b, 102]; // Default ~40% opacity
}
```

- [ ] **Step 2: Commit**

```bash
git add src/segmentation/maskUtils.js
git commit -m "feat: add mask rendering utilities for canvas overlay"
```

---

### Task 4: Create SegmentationOverlay component

**Files:**
- Create: `src/components/SegmentationOverlay.jsx`

- [ ] **Step 1: Create the overlay component**

```jsx
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

    return (
        <canvas
            ref={canvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
            style={{ objectFit: 'contain' }}
        />
    );
};

export default SegmentationOverlay;
```

- [ ] **Step 2: Commit**

```bash
git add src/components/SegmentationOverlay.jsx
git commit -m "feat: add SegmentationOverlay canvas component"
```

---

### Task 5: Add segment_camera tool to backend

**Files:**
- Modify: `backend/ada.py`
- Modify: `backend/server.py`

- [ ] **Step 1: Add tool definition in ada.py**

Add before the `tools = [...]` line:

```python
segment_camera_tool = {
    "name": "segment_camera",
    "description": "Highlights or colors a specific object/area in the camera feed using AI segmentation. Use when the user says 'markiere', 'highlight', 'color', 'zeig mir' about objects in the camera. The segmentation runs in the user's browser on their GPU.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "What to segment, in English (e.g., 'road', 'person', 'car', 'tree', 'building', 'grass'). Use simple English nouns."
            },
            "color": {
                "type": "STRING",
                "description": "CSS color for the overlay (e.g., 'rgba(255,255,0,0.4)', 'red', 'blue'). Default: semi-transparent yellow."
            }
        },
        "required": ["target"]
    }
}
```

Add `segment_camera_tool` to the tools list.

- [ ] **Step 2: Add segment_camera to the tool name check**

Add `"segment_camera"` to the `fc.name in [...]` list.

- [ ] **Step 3: Add dispatch handler in ada.py**

After the `stop_camera` handler:

```python
elif fc.name == "segment_camera":
    target = fc.args["target"]
    color = fc.args.get("color", "rgba(255, 255, 0, 0.4)")
    print(f"[ADA DEBUG] [TOOL] Tool Call: 'segment_camera' target={target} color={color}")

    if self.on_web_data:
        self.on_web_data({
            "type": "segment_request",
            "target": target,
            "color": color,
            "camera": self._active_camera,
        })
    result_str = f"Segmentation request sent for '{target}'. The user's browser will process it."
    function_response = types.FunctionResponse(
        id=fc.id, name=fc.name, response={"result": result_str}
    )
    function_responses.append(function_response)
```

- [ ] **Step 4: Add to default permissions in server.py**

Add `"segment_camera": True` to `DEFAULT_SETTINGS["tool_permissions"]`.

- [ ] **Step 5: Add to SettingsWindow.jsx tools list**

Add `{ id: 'segment_camera', label: 'Segment Camera' }` to the `TOOLS` array.

- [ ] **Step 6: Commit**

```bash
git add backend/ada.py backend/server.py src/components/SettingsWindow.jsx
git commit -m "feat: add segment_camera tool for browser-side segmentation"
```

---

### Task 6: Wire up frontend segmentation pipeline

**Files:**
- Modify: `src/App.jsx`
- Modify: `src/components/CameraFeedWindow.jsx`

- [ ] **Step 1: Add segmentation state and socket handler in App.jsx**

Add state:
```javascript
const [segMasks, setSegMasks] = useState(null); // { masks, width, height }
const [segLoading, setSegLoading] = useState(false);
```

In the `socket.on('browser_frame')` handler, add a case for `segment_request`:
```javascript
if (data.type === 'segment_request') {
    runSegmentation(data.target, data.color, data.camera);
    return;
}
```

Add the segmentation function:
```javascript
const runSegmentation = async (target, color, camera) => {
    setSegLoading(true);
    try {
        const engine = (await import('./segmentation/SegmentationEngine')).default;
        if (!engine.ready) {
            addMessage('System', 'Loading segmentation models (first time may take ~30s)...');
            await engine.load((progress) => {
                console.log(`[SEG] Loading ${progress.model}: ${progress.progress}%`);
            });
            addMessage('System', 'Segmentation models loaded.');
        }

        // Get current snapshot URL
        let imageUrl;
        if (camera && cameraFeed) {
            imageUrl = `${cameraFeed.snapshot_url}?t=${Date.now()}`;
        } else {
            // Webcam: capture current frame to blob URL
            const canvas = transmissionCanvasRef.current;
            if (canvas) {
                const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.9));
                imageUrl = URL.createObjectURL(blob);
            }
        }

        if (!imageUrl) {
            addMessage('System', 'No camera feed active for segmentation.');
            return;
        }

        const result = await engine.segment(imageUrl, target, { color });
        if (result.masks.length === 0) {
            addMessage('System', `Nothing matching "${target}" found in the image.`);
        } else {
            setSegMasks(result);
        }
    } catch (e) {
        console.error('[SEG] Segmentation failed:', e);
        addMessage('System', `Segmentation error: ${e.message}`);
    } finally {
        setSegLoading(false);
    }
};
```

- [ ] **Step 2: Pass segmentation data to CameraFeedWindow**

```jsx
<CameraFeedWindow
    camera={cameraFeed.camera}
    snapshotUrl={cameraFeed.snapshot_url}
    annotations={cameraAnnotations}
    segMasks={segMasks}
    segLoading={segLoading}
    onClose={() => { setCameraFeed(null); setCameraAnnotations([]); setSegMasks(null); }}
/>
```

- [ ] **Step 3: Add SegmentationOverlay to CameraFeedWindow.jsx**

Import and render:
```jsx
import SegmentationOverlay from './SegmentationOverlay';

// Inside the component, after the <img> and annotation SVG:
{segMasks && segMasks.masks.length > 0 && (
    <SegmentationOverlay
        masks={segMasks.masks}
        imgWidth={segMasks.width}
        imgHeight={segMasks.height}
    />
)}
{segLoading && (
    <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-30">
        <span className="text-cyan-400 text-sm font-mono animate-pulse">Segmenting...</span>
    </div>
)}
```

Add `segMasks` and `segLoading` to the component props.

- [ ] **Step 4: Add webcam segmentation overlay in App.jsx**

In the webcam video div, after the existing annotations SVG:
```jsx
{!cameraFeed && segMasks && segMasks.masks.length > 0 && (
    <SegmentationOverlay
        masks={segMasks.masks}
        imgWidth={segMasks.width}
        imgHeight={segMasks.height}
    />
)}
{!cameraFeed && segLoading && (
    <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-30">
        <span className="text-cyan-400 text-sm font-mono animate-pulse">Segmenting...</span>
    </div>
)}
```

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx src/components/CameraFeedWindow.jsx
git commit -m "feat: wire up browser segmentation pipeline end-to-end"
```

---

### Task 7: Final integration commit and push

- [ ] **Step 1: Verify build**

```bash
npm run build
```

Expected: Build succeeds with no errors. Transformers.js is tree-shaken and only loads models at runtime.

- [ ] **Step 2: Push**

```bash
git push origin main
```

---

## Notes

- **First-time model load**: ~30 seconds. Models are cached in browser IndexedDB after that (~1-3s subsequent loads).
- **Inference time**: Grounding DINO ~200ms + SAM encoding ~500ms + SAM decoding ~50ms per detection. Total ~1-2s on RTX 3080 via WebGPU.
- **The `annotate_camera` tool is kept** for simple box/label annotations. `segment_camera` is for pixel-accurate masks.
- **WebGPU fallback**: If WebGPU is not available, the models will fail to load. A WASM fallback could be added later but will be much slower.
- **Gemini's role**: Only intent parsing ("Markiere die Straße" → `segment_camera(target="road")`). All ML runs in the browser.
