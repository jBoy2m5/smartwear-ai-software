"""Scripted sensor simulation; standard library only, no camera acquisition."""
import argparse
import json
import math
import random
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AXES = ('ax', 'ay', 'az', 'gx', 'gy', 'gz')


def validate_config(duration_s, sampling_rate_hz, random_seed, noise_level):
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError('duration_s must be finite and positive')
    if type(sampling_rate_hz) is not int or not 1 <= sampling_rate_hz <= 1000:
        raise ValueError('sampling_rate_hz must be an integer in [1, 1000]')
    if type(random_seed) is not int:
        raise ValueError('random_seed must be an integer')
    if not math.isfinite(noise_level) or not 0 <= noise_level <= 1:
        raise ValueError('noise_level must be finite and in [0, 1]')


def camera_end_ms(path):
    """Read only; preserve the camera's original relative time origin."""
    previous = -1
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            timestamp = json.loads(line)['timestamp_ms']
            if type(timestamp) is not int or timestamp < 0 or timestamp <= previous:
                raise ValueError('Camera timestamps must be nonnegative increasing integers')
            previous = timestamp
    if previous < 0:
        raise ValueError('Camera file is empty')
    return previous


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def simulated_records(duration_s=7.0, sampling_rate_hz=100, random_seed=42,
                      noise_level=0.02, until_timestamp_ms=None):
    """Yield sensor dicts. A future hardware source can yield the same schema.

    Normal duration is end-exclusive. until_timestamp_ms instead includes the
    first sample at or beyond the requested endpoint. Neither mode reads video.
    """
    validate_config(duration_s, sampling_rate_hz, random_seed, noise_level)
    if until_timestamp_ms is None:
        count = int((Decimal(str(duration_s)) * sampling_rate_hz).to_integral_value(
            rounding=ROUND_CEILING))
    else:
        if type(until_timestamp_ms) is not int or until_timestamp_ms < 0:
            raise ValueError('until_timestamp_ms must be a nonnegative integer')
        count = (until_timestamp_ms * sampling_rate_hz + 999) // 1000 + 1
    rng = random.Random(random_seed)

    def noisy(value, scale, lower=None):
        result = value + rng.uniform(-1, 1) * noise_level * scale
        return round(max(lower, result) if lower is not None else result, 6)

    for i in range(count):
        timestamp = i * 1000 // sampling_rate_hz
        t = (timestamp % 7000) / 1000
        # Smooth envelopes vanish at phase boundaries, including the cycle seam.
        reach = math.sin(math.pi * t / 2) ** 2 if t < 2 else 0.0
        release = math.sin(math.pi * (t - 6)) ** 2 if t >= 6 else 0.0
        movement = 0.08 + 2.0 * reach + 0.3 * release
        grip = smooth((t - 2) / 2) if t < 6 else 1 - smooth(t - 6)
        assembly = math.sin(math.pi * (t - 4) / 2) ** 2 if 4 <= t < 6 else 0.0
        angle = 30 * smooth((t - 4) / 2) if t < 6 else 30 * (1 - smooth(t - 6))

        def imu(amplitude):
            return {
                'ax': noisy(amplitude * math.sin(2 * math.pi * t), 1),
                'ay': noisy(amplitude * math.cos(2 * math.pi * t), 1),
                'az': noisy(9.81 + 0.2 * amplitude * math.sin(4 * math.pi * t), 1),
                'gx': noisy(0.4 * amplitude * math.sin(2 * math.pi * t), 0.2),
                'gy': noisy(0.4 * amplitude * math.cos(2 * math.pi * t), 0.2),
                'gz': noisy(0.2 * amplitude * math.sin(4 * math.pi * t), 0.2),
            }

        yield {
            'timestamp_ms': timestamp,
            'imu_head': imu(0.08 + 0.08 * reach),
            'imu_wrist': imu(movement),
            'force_emg_raw': noisy(100 + 700 * grip, 1000, 0),
            'torque': {'torque': noisy(3 * assembly, 3, 0),
                       'angle': noisy(angle, 30, 0)},
        }


def validate_record(record):
    timestamp = record['timestamp_ms']
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError('Invalid timestamp_ms')
    values = [record['force_emg_raw'], record['torque']['torque'], record['torque']['angle']]
    for name in ('imu_head', 'imu_wrist'):
        values.extend(record[name][axis] for axis in AXES)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('Sensor values must be finite numbers')


def read_sensor_records(path):
    """Simple reader interface: iterate over validated sensor dictionaries.

    Consumers accept an iterable of these records; replace this JSONL iterator
    with a hardware iterator later, keeping keys, units and timestamp semantics.
    """
    previous = -1
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            validate_record(record)
            if record['timestamp_ms'] <= previous:
                raise ValueError('Sensor timestamps must strictly increase')
            previous = record['timestamp_ms']
            yield record


def write_sensor_records(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    previous = -1
    # Exclusive creation: never truncate an existing file, even another input.
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        for record in records:
            validate_record(record)
            if record['timestamp_ms'] <= previous:
                raise ValueError('Sensor timestamps must strictly increase')
            stream.write(json.dumps(record, allow_nan=False) + '\n')
            previous = record['timestamp_ms']
            count += 1
    return count, previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-s', type=float, default=7.0)
    parser.add_argument('--sampling-rate-hz', type=int, default=100)
    parser.add_argument('--random-seed', type=int, default=42)
    parser.add_argument('--noise-level', type=float, default=0.02)
    parser.add_argument('--camera-file', type=Path, nargs='?',
                        const=ROOT / 'data/processed/normalized_camera.jsonl')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'data/simulated/sensors_default.jsonl')
    args = parser.parse_args()
    try:
        validate_config(args.duration_s, args.sampling_rate_hz, args.random_seed, args.noise_level)
        end = camera_end_ms(args.camera_file) if args.camera_file is not None else None
        records = simulated_records(args.duration_s, args.sampling_rate_hz,
                                    args.random_seed, args.noise_level, end)
        count, last = write_sensor_records(args.output, records)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'Created {args.output.resolve()}: {count} samples, 0..{last} ms')


if __name__ == '__main__':
    main()
