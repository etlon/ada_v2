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

        const { threshold = 0.3, color = 'rgba(255, 255, 0, 0.4)' } = options;

        const labels = textPrompt.toLowerCase().endsWith('.')
            ? [textPrompt.toLowerCase()]
            : [textPrompt.toLowerCase() + '.'];

        const detections = await this.detector(imageUrl, labels, { threshold });

        if (!detections || detections.length === 0) {
            return { masks: [], message: `Nothing matching "${textPrompt}" found.` };
        }

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

            // iou_scores shape: [1, 1, 3] for single box input → flat [3] scores
            // masks[0] has 3 mask candidates, pick the best by IoU score
            const scores = outputs.iou_scores.data;
            let bestIdx = 0;
            for (let i = 1; i < 3; i++) {
                if (scores[i] > scores[bestIdx]) bestIdx = i;
            }

            results.push({
                label: det.label,
                score: det.score,
                box: det.box,
                mask: masks[0][bestIdx],
                color,
            });
        }

        return { masks: results, width: rawImage.width, height: rawImage.height };
    }
}

const engine = new SegmentationEngine();
export default engine;
