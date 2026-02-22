"""Utilities for packaging trained models for production inference."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Tuple

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    torch = None

try:
    import tensorflow as tf
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tf = None

from ai_ml_services.authenticity.cnn_detector import create_model

logger = logging.getLogger(__name__)


def _require_torch() -> None:
    if torch is None:
        raise RuntimeError(
            "PyTorch is not installed. Install torch to optimize/export PyTorch models."
        )


def _require_tensorflow() -> None:
    if tf is None:
        raise RuntimeError(
            "TensorFlow is not installed. Install tensorflow to quantize TF models."
        )


def _load_authenticity_model(model_path: Path):
    """Load authenticity model state dict and return a ready nn.Module."""
    _require_torch()

    try:
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    except TypeError:
        logger.warning(
            "torch.load(weights_only=True) is not supported in this torch version; "
            "falling back to legacy deserialization for %s",
            model_path,
        )
        checkpoint = torch.load(model_path, map_location="cpu")
    state_dict = (
        checkpoint.get("model_state_dict")
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint
        else checkpoint
    )

    if not isinstance(state_dict, dict):
        raise ValueError(
            "Unsupported checkpoint format. Expected a state_dict or dict containing "
            "'model_state_dict'."
        )

    model = create_model("resnet18", pretrained=False)
    incompatible = model.load_state_dict(state_dict, strict=False)
    if incompatible.missing_keys:
        logger.warning(
            "Missing keys while loading checkpoint: %s", incompatible.missing_keys
        )
    if incompatible.unexpected_keys:
        logger.warning(
            "Unexpected keys while loading checkpoint: %s",
            incompatible.unexpected_keys,
        )
    model.eval()
    return model


class ModelDeployer:
    """Deploy trained models for production."""

    @staticmethod
    def optimize_pytorch_model(
        model_path: str,
        output_path: str,
        input_shape: Tuple[int, int, int, int] = (1, 3, 224, 224),
    ) -> None:
        """Optimize a PyTorch authenticity model to TorchScript."""
        _require_torch()

        model_path = Path(model_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Loading PyTorch model from %s", model_path)
        model = _load_authenticity_model(model_path)

        logger.info("Tracing model with input shape %s", input_shape)
        example_input = torch.randn(input_shape)
        traced_model = torch.jit.trace(model, example_input)
        traced_model.save(output_path)
        logger.info("Optimized TorchScript model saved to %s", output_path)

    @staticmethod
    def quantize_tensorflow_model(
        model_path: str,
        output_path: str,
        quantization_type: str = "DEFAULT",
    ) -> None:
        """Quantize a TensorFlow Keras model to TFLite."""
        _require_tensorflow()

        model_path = Path(model_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Loading TensorFlow model from %s", model_path)
        model = tf.keras.models.load_model(model_path)

        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        quantization_type = quantization_type.upper()

        if quantization_type == "DEFAULT":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
        elif quantization_type == "FLOAT16":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]
        elif quantization_type == "INT8":
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type = tf.int8
            converter.inference_output_type = tf.int8
            logger.warning(
                "INT8 conversion without representative dataset uses dynamic range "
                "quantization semantics."
            )
        else:
            logger.warning(
                "Unknown quantization_type=%s. Continuing without extra quantization.",
                quantization_type,
            )

        tflite_model = converter.convert()
        output_path.write_bytes(tflite_model)
        logger.info("TFLite model saved to %s", output_path)

    @staticmethod
    def export_to_onnx(
        model_path: str,
        output_path: str,
        input_shape: Tuple[int, int, int, int] = (1, 3, 224, 224),
        opset_version: int = 11,
    ) -> None:
        """Export a PyTorch authenticity model checkpoint to ONNX."""
        _require_torch()

        model_path = Path(model_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Loading PyTorch model from %s for ONNX export", model_path)
        model = _load_authenticity_model(model_path)

        dummy_input = torch.randn(input_shape, requires_grad=True)
        torch.onnx.export(
            model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        )
        logger.info("ONNX model saved to %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy trained models.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    pytorch_parser = subparsers.add_parser(
        "pytorch", help="Optimize PyTorch model to TorchScript."
    )
    pytorch_parser.add_argument(
        "--model_path", type=str, required=True, help="Input PyTorch checkpoint (.pth)."
    )
    pytorch_parser.add_argument(
        "--output_path",
        type=str,
        required=True,
        help="Output TorchScript model path (.pt).",
    )
    pytorch_parser.add_argument(
        "--input_shape",
        type=int,
        nargs="+",
        default=[1, 3, 224, 224],
        help="Input shape for tracing, e.g. 1 3 224 224.",
    )

    tf_parser = subparsers.add_parser(
        "tensorflow", help="Quantize TensorFlow model to TFLite."
    )
    tf_parser.add_argument(
        "--model_path",
        type=str,
        required=True,
        help="Input TensorFlow model (.h5 or SavedModel).",
    )
    tf_parser.add_argument(
        "--output_path",
        type=str,
        required=True,
        help="Output TFLite model path (.tflite).",
    )
    tf_parser.add_argument(
        "--quantization_type",
        type=str,
        default="DEFAULT",
        choices=["DEFAULT", "FLOAT16", "INT8"],
        help="Quantization strategy.",
    )

    onnx_parser = subparsers.add_parser("onnx", help="Export PyTorch model to ONNX.")
    onnx_parser.add_argument(
        "--model_path", type=str, required=True, help="Input PyTorch checkpoint (.pth)."
    )
    onnx_parser.add_argument(
        "--output_path", type=str, required=True, help="Output ONNX model path (.onnx)."
    )
    onnx_parser.add_argument(
        "--input_shape",
        type=int,
        nargs="+",
        default=[1, 3, 224, 224],
        help="Input shape for export, e.g. 1 3 224 224.",
    )
    onnx_parser.add_argument(
        "--opset_version", type=int, default=11, help="ONNX opset version."
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.command == "pytorch":
        ModelDeployer.optimize_pytorch_model(
            args.model_path, args.output_path, tuple(args.input_shape)
        )
    elif args.command == "tensorflow":
        ModelDeployer.quantize_tensorflow_model(
            args.model_path, args.output_path, args.quantization_type
        )
    elif args.command == "onnx":
        ModelDeployer.export_to_onnx(
            args.model_path, args.output_path, tuple(args.input_shape), args.opset_version
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
