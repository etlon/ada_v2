import { pipeline, SamModel, AutoProcessor, RawImage } from '@huggingface/transformers';

const DETECTION_MODEL = 'onnx-community/owlv2-base-patch16-ensemble-ONNX';
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
            const makeProgressCb = (modelName) => (event) => {
                if (this.onProgress && event.status === 'progress') {
                    this.onProgress({
                        model: modelName,
                        progress: Math.round(event.progress || 0),
                        file: event.file || '',
                        loaded: event.loaded || 0,
                        total: event.total || 0,
                    });
                } else if (this.onProgress && event.status === 'done') {
                    this.onProgress({ model: modelName, progress: 100, file: event.file || '' });
                } else if (this.onProgress && event.status === 'initiate') {
                    this.onProgress({ model: modelName, progress: 0, file: event.file || '', status: 'downloading' });
                }
            };

            if (this.onProgress) this.onProgress({ model: 'OWLv2 Detector', progress: 0, status: 'downloading' });
            this.detector = await pipeline('zero-shot-object-detection', DETECTION_MODEL, {
                device: 'webgpu',
                dtype: 'q4',
                progress_callback: makeProgressCb('OWLv2 Detector'),
            });
            if (this.onProgress) this.onProgress({ model: 'OWLv2 Detector', progress: 100 });

            if (this.onProgress) this.onProgress({ model: 'SlimSAM', progress: 0, status: 'downloading' });
            this.samModel = await SamModel.from_pretrained(SAM_MODEL, {
                device: 'webgpu',
                dtype: {
                    vision_encoder: 'fp16',
                    prompt_encoder_mask_decoder: 'fp16',
                },
                progress_callback: makeProgressCb('SlimSAM'),
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

        const labels = [textPrompt.toLowerCase().trim()];

        console.log('[SEG] Image URL:', imageUrl);
        console.log('[SEG] Detecting with labels:', labels, 'threshold:', threshold);

        // Try multiple thresholds if needed
        let detections = await this.detector(imageUrl, labels, { threshold });
        console.log('[SEG] Detections at threshold', threshold, ':', JSON.stringify(detections));

        // If nothing found, try with even lower threshold
        if ((!detections || detections.length === 0) && threshold > 0.05) {
            console.log('[SEG] Retrying with lower threshold 0.05...');
            detections = await this.detector(imageUrl, labels, { threshold: 0.05 });
            console.log('[SEG] Detections at threshold 0.05:', JSON.stringify(detections));
        }

        if (!detections || detections.length === 0) {
            return { masks: [], message: `Nothing matching "${textPrompt}" found.` };
        }

        // Keep only top 3 detections by score to avoid false positives
        detections.sort((a, b) => b.score - a.score);
        detections = detections.slice(0, 3);

        const rawImage = await RawImage.read(imageUrl);
        const results = [];

        console.log('[SEG] Processing', detections.length, 'detections on', rawImage.width, 'x', rawImage.height, 'image');

        for (const det of detections) {
            try {
                const { xmin, ymin, xmax, ymax } = det.box;
                console.log('[SEG] Detection:', det.label, 'score:', det.score, 'box:', xmin, ymin, xmax, ymax);

                const cx = Math.round((xmin + xmax) / 2);
                const cy = Math.round((ymin + ymax) / 2);
                const input_points = [[[cx, cy]]];

                const inputs = await this.samProcessor(rawImage, { input_points });
                const outputs = await this.samModel(inputs);

                const scores = outputs.iou_scores.data;
                let bestIdx = 0;
                for (let i = 1; i < 3; i++) {
                    if (scores[i] > scores[bestIdx]) bestIdx = i;
                }

                // Try post_process_masks to get full-resolution mask
                let maskData, maskH, maskW;
                try {
                    const processed = await this.samProcessor.post_process_masks(
                        outputs.pred_masks,
                        inputs.original_sizes,
                        inputs.reshaped_input_sizes
                    );
                    console.log('[SEG] post_process_masks result type:', typeof processed, Array.isArray(processed) ? 'array len=' + processed.length : '');

                    // Inspect structure
                    const first = processed[0];
                    console.log('[SEG] processed[0] type:', typeof first, first?.dims ? 'tensor dims=' + first.dims : (Array.isArray(first) ? 'array len=' + first.length : ''));

                    let maskTensor;
                    if (first?.dims) {
                        // It's a tensor directly — shape might be [num_masks, H, W]
                        maskTensor = first;
                    } else if (Array.isArray(first) && first[bestIdx]?.dims) {
                        maskTensor = first[bestIdx];
                    } else if (first?.[0]?.dims) {
                        maskTensor = first[0];
                    }

                    if (maskTensor) {
                        const dims = maskTensor.dims;
                        console.log('[SEG] maskTensor dims:', dims);
                        // Could be [num_masks, H, W] or [H, W]
                        if (dims.length === 3) {
                            maskH = dims[1];
                            maskW = dims[2];
                            const maskSize = maskH * maskW;
                            const offset = bestIdx * maskSize;
                            maskData = new Uint8Array(maskSize);
                            for (let i = 0; i < maskSize; i++) {
                                maskData[i] = maskTensor.data[offset + i] > 0 ? 1 : 0;
                            }
                        } else if (dims.length === 2) {
                            maskH = dims[0];
                            maskW = dims[1];
                            maskData = new Uint8Array(maskH * maskW);
                            for (let i = 0; i < maskData.length; i++) {
                                maskData[i] = maskTensor.data[i] > 0 ? 1 : 0;
                            }
                        }
                    }
                } catch (ppErr) {
                    console.warn('[SEG] post_process_masks failed, falling back to raw pred_masks:', ppErr.message);
                }

                // Fallback to raw pred_masks if post-processing failed
                if (!maskData) {
                    const pm = outputs.pred_masks;
                    const dims = pm.dims;
                    maskH = dims[dims.length - 2];
                    maskW = dims[dims.length - 1];
                    const maskSize = maskH * maskW;
                    const offset = bestIdx * maskSize;
                    maskData = new Uint8Array(maskSize);
                    for (let i = 0; i < maskSize; i++) {
                        maskData[i] = pm.data[offset + i] > 0 ? 1 : 0;
                    }
                    console.log('[SEG] Using raw pred_masks fallback:', maskH, 'x', maskW);
                }

                results.push({
                    label: det.label,
                    score: det.score,
                    box: det.box,
                    mask: { data: maskData, dims: [maskH, maskW] },
                    color,
                });
                console.log('[SEG] Mask ready:', maskH, 'x', maskW, 'score:', scores[bestIdx].toFixed(3));
            } catch (e) {
                console.error('[SEG] Failed to segment detection:', det.label, e);
            }
        }

        return { masks: results, width: rawImage.width, height: rawImage.height };
    }
}

const engine = new SegmentationEngine();
export default engine;
