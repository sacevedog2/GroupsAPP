from __future__ import annotations

from pathlib import Path


def ensure_generated() -> Path:
    current_dir = Path(__file__).resolve().parent
    proto_dir = current_dir / "proto"
    proto_file = proto_dir / "messaging.proto"
    output_dir = current_dir / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    init_file = output_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")

    pb2_file = output_dir / "messaging_pb2.py"
    pb2_grpc_file = output_dir / "messaging_pb2_grpc.py"

    must_generate = (
        not pb2_file.exists()
        or not pb2_grpc_file.exists()
        or pb2_file.stat().st_mtime < proto_file.stat().st_mtime
        or pb2_grpc_file.stat().st_mtime < proto_file.stat().st_mtime
    )

    if must_generate:
        from grpc_tools import protoc

        result = protoc.main(
            [
                "",
                f"-I{proto_dir}",
                f"--python_out={output_dir}",
                f"--grpc_python_out={output_dir}",
                str(proto_file),
            ]
        )
        if result != 0:
            raise RuntimeError(f"Error generando gRPC codegen. Exit code={result}")

    return output_dir


if __name__ == "__main__":
    ensure_generated()
