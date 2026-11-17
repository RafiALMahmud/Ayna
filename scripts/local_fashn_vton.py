"""Small offline CLI boundary for the optional FASHN VTON environment."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROCESS_STARTED = time.perf_counter()

EVENT_PREFIX = "AYNA_STAGE "


def emit(stage: str, event: str, started: float, **metadata) -> None:
    payload = {
        "stage": stage,
        "event": event,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if metadata:
        payload["metadata"] = metadata
    print(EVENT_PREFIX + json.dumps(payload, sort_keys=True), flush=True)


class CallStageProxy:
    def __init__(
        self,
        target,
        stage: str,
        started: float,
        expected_calls: int = 1,
        callback=None,
    ):
        self.target = target
        self.stage = stage
        self.started = started
        self.expected_calls = expected_calls
        self.calls = 0
        self.callback = callback

    def __getattr__(self, name):
        return getattr(self.target, name)

    def __call__(self, *args, **kwargs):
        if self.calls == 0:
            emit(self.stage, "started", self.started)
        result = self.target(*args, **kwargs)
        if self.callback:
            self.callback(self.calls, args, result)
        self.calls += 1
        if self.calls == self.expected_calls:
            emit(self.stage, "completed", self.started)
        return result


class PredictStageProxy:
    def __init__(self, target, started: float, callback=None):
        self.target = target
        self.started = started
        self.calls = 0
        self.callback = callback

    def __getattr__(self, name):
        return getattr(self.target, name)

    def predict(self, *args, **kwargs):
        if self.calls == 0:
            emit("human_parsing", "started", self.started)
        result = self.target.predict(*args, **kwargs)
        if self.callback:
            self.callback(self.calls, result)
        self.calls += 1
        if self.calls == 2:
            emit("human_parsing", "completed", self.started)
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--person", required=True)
    parser.add_argument("--garment", required=True)
    parser.add_argument(
        "--category", choices=["tops", "bottoms", "one-pieces"], required=True
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-id", default="debug")
    parser.add_argument("--debug-dir")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--skin-recovery",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--restore", action=argparse.BooleanOptionalAction, default=False
    )
    args = parser.parse_args()

    import numpy as np
    import onnxruntime as ort
    import torch
    from fashn_human_parser import IDS_TO_LABELS
    from fashn_human_parser import FashnHumanParser as UpstreamHumanParser
    from PIL import Image, ImageDraw

    backend_path = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend_path))
    from app.modules.tryon.preservation import (
        build_preservation_plan,
        composite_original_resolution,
        mask_pixels,
    )
    from app.modules.tryon.restoration import restore_edit_region

    debug_root = None
    if args.debug_dir:
        safe_job_id = "".join(
            character
            for character in args.job_id
            if character.isalnum() or character == "-"
        )
        debug_root = Path(args.debug_dir) / (safe_job_id[:64] or "debug")
        debug_root.mkdir(parents=True, exist_ok=True)

    label_colors = np.array(
        [
            [0, 0, 0],
            [192, 64, 64],
            [128, 64, 192],
            [64, 128, 255],
            [64, 192, 255],
            [192, 128, 255],
            [64, 192, 128],
            [192, 160, 64],
            [128, 96, 64],
            [255, 128, 192],
            [128, 192, 255],
            [192, 192, 255],
            [255, 160, 64],
            [255, 224, 160],
            [160, 224, 128],
            [192, 255, 192],
            [224, 160, 128],
            [255, 224, 64],
        ],
        dtype=np.uint8,
    )

    def save_debug_image(name: str, image) -> None:
        if debug_root is None:
            return
        if isinstance(image, np.ndarray):
            if image.dtype == bool:
                image = image.astype(np.uint8) * 255
            image = Image.fromarray(image.astype(np.uint8))
        image.save(debug_root / name, "PNG")

    def save_label_map(name: str, labels: np.ndarray) -> None:
        if debug_root is None:
            return
        save_debug_image(name.replace(".png", "_ids.png"), labels.astype(np.uint8))
        colorized = label_colors[
            np.clip(labels.astype(np.int16), 0, len(label_colors) - 1)
        ]
        visualization = Image.fromarray(colorized)
        legend_width = 220
        canvas = Image.new(
            "RGB", (visualization.width + legend_width, visualization.height), "white"
        )
        canvas.paste(visualization, (0, 0))
        draw = ImageDraw.Draw(canvas)
        for label_id, label_name in IDS_TO_LABELS.items():
            y = 8 + label_id * 22
            color = tuple(int(value) for value in label_colors[label_id])
            draw.rectangle(
                (visualization.width + 8, y, visualization.width + 24, y + 16),
                fill=color,
            )
            draw.text(
                (visualization.width + 30, y), f"{label_id}: {label_name}", fill="black"
            )
        canvas.save(debug_root / name, "PNG")

    started = PROCESS_STARTED
    emit(
        "process_startup",
        "completed",
        started,
        torch_version=torch.__version__,
        torch_cuda=torch.version.cuda,
        cuda_available=torch.cuda.is_available(),
        cuda_device=torch.cuda.get_device_name(0)
        if torch.cuda.is_available()
        else None,
        ort_version=ort.__version__,
        ort_available_providers=ort.get_available_providers(),
    )

    # ONNX Runtime 1.31 requires CUDA 13/cuDNN 9, while this verified PyTorch runtime is
    # CUDA 12.8. Use an explicit, bounded CPU session for DWPose instead of triggering a
    # noisy failed CUDA provider load and an implicit fallback. Main synthesis remains CUDA.
    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 2) // 2))
    session_options.inter_op_num_threads = 1
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    original_session = ort.InferenceSession

    def bounded_session(*session_args, **session_kwargs):
        session_kwargs["sess_options"] = session_options
        session_kwargs["providers"] = ["CPUExecutionProvider"]
        session_kwargs.pop("provider_options", None)
        return original_session(*session_args, **session_kwargs)

    ort.InferenceSession = bounded_session

    from fashn_vton import TryOnPipeline as UpstreamTryOnPipeline
    from fashn_vton import pipeline as pipeline_module
    from fashn_vton.dwpose import DWposeDetector, draw_pose

    parser_path = Path(args.weights) / "parser"
    if not parser_path.is_dir():
        raise FileNotFoundError("Pinned local human parser weights are missing")

    class LocalHumanParser(UpstreamHumanParser):
        def __init__(self, device=None):
            super().__init__(model_id=str(parser_path), device=device)

    pipeline_module.FashnHumanParser = LocalHumanParser

    preprocessing_calls = 0
    person_labels = None
    garment_labels = None
    original_clothing = pipeline_module.create_clothing_agnostic_image
    original_garment = pipeline_module.create_garment_image

    def staged_clothing(*call_args, **call_kwargs):
        nonlocal preprocessing_calls
        if preprocessing_calls == 0:
            emit("garment_preprocessing", "started", started)
        if debug_root is not None and call_kwargs:
            original_image = call_kwargs["img_np"].copy()
            debug_kwargs = {
                **call_kwargs,
                "img_np": original_image.copy(),
                "seg_pred": call_kwargs["seg_pred"].copy(),
                "labels_to_segment_indices": list(
                    call_kwargs["labels_to_segment_indices"]
                ),
                "disable_masking": False,
            }
            debug_ca_image = original_clothing(**debug_kwargs)
            replacement_mask = np.any(debug_ca_image != original_image, axis=2)
            save_debug_image("07_garment_replacement_mask.png", replacement_mask)
            save_debug_image("08_clothing_agnostic.png", debug_ca_image)
        result = original_clothing(*call_args, **call_kwargs)
        preprocessing_calls += 1
        return result

    def staged_garment(*call_args, **call_kwargs):
        nonlocal preprocessing_calls
        if preprocessing_calls == 0:
            emit("garment_preprocessing", "started", started)
        result = original_garment(*call_args, **call_kwargs)
        preprocessing_calls += 1
        save_debug_image(
            "09_garment_prepared.png",
            result,
        )
        if preprocessing_calls == 2:
            emit("garment_preprocessing", "completed", started)
        return result

    pipeline_module.create_clothing_agnostic_image = staged_clothing
    pipeline_module.create_garment_image = staged_garment

    class StagedTryOnPipeline(UpstreamTryOnPipeline):
        def _setup_pose_model(self):
            dwpose_dir = str(Path(self.weights_dir) / "dwpose")
            self.pose_model = DWposeDetector(checkpoints_dir=dwpose_dir, device="cpu")

        def _sample(self, **kwargs):
            emit("cuda_synthesis", "started", started)
            result = super()._sample(**kwargs)
            if result:
                save_debug_image("10a_internal_padded_sample.png", result[0])
            emit(
                "cuda_synthesis",
                "completed",
                started,
                cuda_peak_mib=(
                    round(torch.cuda.max_memory_allocated() / 1024**2, 2)
                    if torch.cuda.is_available()
                    else None
                ),
                candidate_seed=args.seed,
            )
            return result

    emit("model_loading", "started", started)
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    torch.set_num_threads(max(1, min(4, (os.cpu_count() or 2) // 2)))
    torch.set_num_interop_threads(1)
    pipeline = StagedTryOnPipeline(weights_dir=args.weights)

    def capture_pose(call_index, call_args, pose) -> None:
        if debug_root is None:
            return
        source_image = call_args[0]
        height, width = source_image.shape[:2]
        rendered = draw_pose(pose, height, width, grayscale=False)
        save_debug_image(
            "03_pose_person.png" if call_index == 0 else "04_pose_garment.png", rendered
        )

    def capture_parser(call_index, labels) -> None:
        nonlocal garment_labels, person_labels
        if call_index == 0:
            person_labels = labels.copy()
        elif call_index == 1:
            garment_labels = labels.copy()
        save_label_map(
            "05_parser_person_labels.png"
            if call_index == 0
            else "06_parser_garment_labels.png",
            labels,
        )

    pipeline.pose_model = CallStageProxy(
        pipeline.pose_model,
        "pose_detection",
        started,
        2,
        callback=capture_pose,
    )
    pipeline.hp_model = PredictStageProxy(
        pipeline.hp_model, started, callback=capture_parser
    )
    emit(
        "model_loading",
        "completed",
        started,
        synthesis_device=str(pipeline.device),
        synthesis_dtype=str(pipeline.inference_dtype),
        pose_providers=["CPUExecutionProvider"],
        pose_fallback_reason="ONNX Runtime 1.31 requires CUDA 13; PyTorch runtime uses CUDA 12.8",
        cpu_threads=torch.get_num_threads(),
    )
    person_input = Image.open(args.person).convert("RGB")
    garment_input = Image.open(args.garment).convert("RGB")
    save_debug_image("01_input_person.png", person_input)
    save_debug_image("02_input_garment.png", garment_input)
    result = pipeline(
        person_image=person_input,
        garment_image=garment_input,
        category=args.category,
        seed=args.seed,
    )
    baseline = result.images[0]
    save_debug_image("10_raw_model_output.png", baseline)
    emit("output_parsing", "started", started)
    output_labels = pipeline.hp_model.target.predict(
        np.asarray(baseline.convert("RGB"))
    )
    save_label_map("10b_parser_output_labels.png", output_labels)
    emit("output_parsing", "completed", started, parser_device="cpu")
    plan = build_preservation_plan(
        person_input,
        baseline,
        Image.fromarray(person_labels.astype(np.uint8)),
        Image.fromarray(output_labels.astype(np.uint8)),
    )
    save_debug_image("10c_output_garment_region.png", plan.garment_region)
    save_debug_image("10d_preserve_mask.png", plan.preserve_mask)
    save_debug_image("10e_newly_exposed_skin.png", plan.newly_exposed_skin)
    save_debug_image("10f_visible_skin.png", plan.visible_skin)
    newly_exposed_pixels = mask_pixels(plan.newly_exposed_skin)
    recovery_metadata = {
        "skin_recovery_applied": bool(args.skin_recovery and newly_exposed_pixels),
        "skin_recovery_seconds": 0.0,
        "sam2_refinement": "skipped_vram_budget",
        "candidate_seed": args.seed,
        "preserved_pixels": mask_pixels(plan.preserve_mask),
        "newly_exposed_skin_pixels": newly_exposed_pixels,
    }
    recovery_started = time.perf_counter()
    if args.skin_recovery and newly_exposed_pixels:
        emit("skin_recovery", "started", started)
    result.images[0] = composite_original_resolution(
        person_input,
        baseline,
        plan,
        recover_new_skin=args.skin_recovery,
    )
    recovery_metadata["skin_recovery_seconds"] = round(
        time.perf_counter() - recovery_started, 3
    )
    if args.skin_recovery and newly_exposed_pixels:
        emit("skin_recovery", "completed", started, **recovery_metadata)
    restoration_metadata = {
        "restoration_applied": args.restore,
        "restoration_method": "classical_unsharp_mask" if args.restore else None,
        "restoration_seconds": 0.0,
    }
    if args.restore:
        emit("detail_restoration", "started", started)
        restoration_started = time.perf_counter()
        result.images[0] = restore_edit_region(person_input, result.images[0], plan)
        restoration_metadata["restoration_seconds"] = round(
            time.perf_counter() - restoration_started, 3
        )
        emit("detail_restoration", "completed", started, **restoration_metadata)
    del pipeline
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    emit("image_encoding", "started", started)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.images[0].save(output, "PNG", optimize=True)
    save_debug_image("11_final_composite.png", result.images[0])
    emit("image_encoding", "completed", started)
    print(
        json.dumps(
            {
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "device": "cuda:0" if torch.cuda.is_available() else "cpu",
                "peak_cuda_mib": (
                    round(torch.cuda.max_memory_allocated() / 1024**2, 2)
                    if torch.cuda.is_available()
                    else None
                ),
                **recovery_metadata,
                **restoration_metadata,
            }
        )
    )


if __name__ == "__main__":
    main()
