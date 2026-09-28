"""Robot JSON and ROS2 bag artifact generation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore

from backend.schemas import SessionInput


@dataclass(frozen=True, slots=True)
class RobotArtifacts:
    """Paths generated for one robot dataset export."""

    json_path: Path
    db3_path: Path
    metadata_path: Path
    archive_path: Path


class RobotDatasetExporter:
    """Export validated trajectories as JSON and ROS2 bag artifacts."""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir

    def export(self, payload: SessionInput) -> RobotArtifacts:
        """Generate all robot artifacts atomically where practical."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        bag_name = f"rosbag_{payload.session_id}"
        bag_dir = self.artifact_dir / bag_name
        json_path = self.artifact_dir / f"robot_dataset_{payload.session_id}.json"
        db3_path = self.artifact_dir / f"{bag_name}.db3"
        archive_path = self.artifact_dir / f"{bag_name}.zip"

        self._write_json(json_path, payload)
        staging_root = Path(tempfile.mkdtemp(dir=self.artifact_dir, prefix=f".{bag_name}_"))
        staged_bag = staging_root / bag_name
        try:
            self._write_rosbag(staged_bag, payload)
            self._replace_directory(staged_bag, bag_dir)
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

        bag_db3 = next(bag_dir.glob("*.db3"))
        metadata_path = bag_dir / "metadata.yaml"
        self._atomic_copy(bag_db3, db3_path)
        self._write_archive(archive_path, bag_name, bag_db3, metadata_path)
        return RobotArtifacts(
            json_path=json_path.resolve(),
            db3_path=db3_path.resolve(),
            metadata_path=metadata_path.resolve(),
            archive_path=archive_path.resolve(),
        )

    @staticmethod
    def _dataset(payload: SessionInput) -> dict[str, object]:
        pose_messages: list[dict[str, object]] = []
        wrench_messages: list[dict[str, object]] = []
        for point in payload.robot_trajectory_points:
            timestamp_ns = int(round(point.t * 1_000_000_000))
            seconds, nanoseconds = divmod(timestamp_ns, 1_000_000_000)
            stamp = {"sec": seconds, "nanosec": nanoseconds}
            x, y, z = point.pos
            pose_messages.append(
                {
                    "header": {"stamp": stamp, "frame_id": "base_link"},
                    "pose": {
                        "position": {"x": x, "y": y, "z": z},
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                }
            )
            wrench_messages.append(
                {
                    "header": {"stamp": stamp, "frame_id": "base_link"},
                    "wrench": {
                        "force": {"x": 0.0, "y": 0.0, "z": point.force},
                        "torque": {"x": 0.0, "y": 0.0, "z": 0.0},
                    },
                }
            )
        return {
            "session_id": payload.session_id,
            "serialization_format": "json",
            "frame_id": "base_link",
            "topics": [
                {
                    "name": "/arm_cartesian_trajectory",
                    "type": "geometry_msgs/msg/PoseStamped",
                    "messages": pose_messages,
                },
                {
                    "name": "/end_effector_wrench",
                    "type": "geometry_msgs/msg/WrenchStamped",
                    "messages": wrench_messages,
                },
            ],
        }

    def _write_json(self, destination: Path, payload: SessionInput) -> None:
        content = json.dumps(self._dataset(payload), ensure_ascii=True, indent=2, allow_nan=False)
        temporary = self._temporary_path(".json.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _write_rosbag(bag_dir: Path, payload: SessionInput) -> None:
        typestore = get_typestore(Stores.ROS2_HUMBLE)
        time_type = typestore.types["builtin_interfaces/msg/Time"]
        header_type = typestore.types["std_msgs/msg/Header"]
        point_type = typestore.types["geometry_msgs/msg/Point"]
        quaternion_type = typestore.types["geometry_msgs/msg/Quaternion"]
        pose_type = typestore.types["geometry_msgs/msg/Pose"]
        pose_stamped_type = typestore.types["geometry_msgs/msg/PoseStamped"]
        vector_type = typestore.types["geometry_msgs/msg/Vector3"]
        wrench_type = typestore.types["geometry_msgs/msg/Wrench"]
        wrench_stamped_type = typestore.types["geometry_msgs/msg/WrenchStamped"]

        with Writer(bag_dir, version=9) as writer:
            pose_connection = writer.add_connection(
                "/arm_cartesian_trajectory",
                pose_stamped_type.__msgtype__,
                typestore=typestore,
            )
            wrench_connection = writer.add_connection(
                "/end_effector_wrench",
                wrench_stamped_type.__msgtype__,
                typestore=typestore,
            )
            for point in payload.robot_trajectory_points:
                timestamp_ns = int(round(point.t * 1_000_000_000))
                seconds, nanoseconds = divmod(timestamp_ns, 1_000_000_000)
                header = header_type(time_type(sec=seconds, nanosec=nanoseconds), "base_link")
                x, y, z = point.pos
                pose = pose_stamped_type(
                    header,
                    pose_type(
                        point_type(x=x, y=y, z=z),
                        quaternion_type(x=0.0, y=0.0, z=0.0, w=1.0),
                    ),
                )
                wrench = wrench_stamped_type(
                    header,
                    wrench_type(
                        vector_type(x=0.0, y=0.0, z=point.force),
                        vector_type(x=0.0, y=0.0, z=0.0),
                    ),
                )
                writer.write(
                    pose_connection,
                    timestamp_ns,
                    typestore.serialize_cdr(pose, pose_stamped_type.__msgtype__),
                )
                writer.write(
                    wrench_connection,
                    timestamp_ns,
                    typestore.serialize_cdr(wrench, wrench_stamped_type.__msgtype__),
                )

    def _atomic_copy(self, source: Path, destination: Path) -> None:
        temporary = self._temporary_path(".db3.tmp")
        try:
            shutil.copyfile(source, temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_archive(
        self,
        destination: Path,
        bag_name: str,
        db3_path: Path,
        metadata_path: Path,
    ) -> None:
        temporary = self._temporary_path(".zip.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(db3_path, f"{bag_name}/{db3_path.name}")
                archive.write(metadata_path, f"{bag_name}/metadata.yaml")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _temporary_path(self, suffix: str) -> Path:
        handle = tempfile.NamedTemporaryFile(dir=self.artifact_dir, suffix=suffix, delete=False)
        handle.close()
        return Path(handle.name)

    @staticmethod
    def _replace_directory(source: Path, destination: Path) -> None:
        backup = destination.with_name(f".{destination.name}.old")
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(source, destination)
        except Exception:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        finally:
            if backup.exists():
                shutil.rmtree(backup)

