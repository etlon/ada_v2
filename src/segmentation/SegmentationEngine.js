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
        this.onProgress = null;
    }

    async load(onProgress) {
        if (this.ready || this.loading) return;
        this.loading = true;
        this.onProgress = onProgress || null;

        try {
            if (this.onProgress) this.onProgress({ model: 'Grounding DINO', progress: 0 });
            this.detector = await pipeline('zero-shot-object-detection', GROUNDING_DINO_MODEL, {
                device: 'webgpu',
                dtype: 'fp32',
            });
            if (this.onProgress) this.onProgress({ model: 'Grounding DINO', progress: 100 });

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

        const { threshold = 0.15, color = 'rgba(255, 255, 0, 0.4)' } = options;

        const labels = textPrompt.toLowerCase().endsWith('.')
            ? [textPrompt.toLowerCase()]
            : [textPrompt.toLowerCase() + '.'];

        console.log('[SEG] Detecting with labels:', labels, 'threshold:', threshold);
        const detections = await this.detector(imageUrl, labels, { threshold });
        console.log('[SEG] Detections:', detections);

        if (!detections || detections.length === 0) {
            return { masks: [], message: `Nothing matching "${textPrompt}" found.` };
        }

        const rawImage = await RawImage.read(imageUrl);
        const results = [];

        // Phase 1: Encode image once (expensive)
        const baseInputs = await this.samProcessor(rawImage);
        const imageEmbeddings = await this.samModel.get_image_embeddings(baseInputs);
        console.log('[SEG] Image encoded. Processing', detections.length, 'detections');

        // Phase 2: Decode each detection (cheap)
        for (const det of detections) {
            try {
                const { xmin, ymin, xmax, ymax } = det.box;
                const input_boxes = [[[xmin, ymin, xmax, ymax]]];

                const inputs = await this.samProcessor(rawImage, { input_boxes });
                const outputs = await this.samModel({
                    ...inputs,
                    ...imageEmbeddings,
                });

                const pm = outputs.pred_masks;
                console.log('[SEG] pred_masks dims:', pm.dims);

                const scores = outputs.iou_scores.data;
                let bestIdx = 0;
                for (let i = 1; i < 3; i++) {
                    if (scores[i] > scores[bestIdx]) bestIdx = i;
                }

                // Extract best mask from pred_masks tensor
                const dims = pm.dims;
                const h = dims[dims.length - 2];
                const w = dims[dims.length - 1];
                const maskSize = h * w;
                const offset = bestIdx * maskSize;
                const maskData = new Uint8Array(maskSize);
                for (let i = 0; i < maskSize; i++) {
                    maskData[i] = pm.data[offset + i] > 0 ? 1 : 0;
                }

                results.push({
                    label: det.label,
                    score: det.score,
                    box: det.box,
                    mask: { data: maskData, dims: [h, w] },
                    color,
                });
                console.log('[SEG] Mask extracted:', h, 'x', w, 'score:', scores[bestIdx].toFixed(3));
            } catch (e) {
                console.error('[SEG] Failed to segment detection:', det.label, e);
            }
        }

        return { masks: results, width: rawImage.width, height: rawImage.height };
    }
}

const engine = new SegmentationEngine();
export default engine;
