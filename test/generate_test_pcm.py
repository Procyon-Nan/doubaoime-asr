from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate PCM s16le test audio")
    parser.add_argument("output", nargs="?", default="./test/test_audio.pcm")
    parser.add_argument("--duration", type=float, default=2.0, help="Audio duration in seconds")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Sample rate")
    parser.add_argument("--frequency", type=float, default=440.0, help="Sine wave frequency")
    parser.add_argument("--amplitude", type=float, default=0.3, help="Amplitude from 0.0 to 1.0")
    parser.add_argument("--wav", action="store_true", help="Also write a wav file next to the pcm file")
    return parser


def generate_pcm_bytes(duration: float, sample_rate: int, frequency: float, amplitude: float) -> bytes:
    sample_count = max(int(duration * sample_rate), 1)
    amplitude = min(max(amplitude, 0.0), 1.0)
    max_value = int(32767 * amplitude)
    buffer = bytearray()
    for index in range(sample_count):
        value = int(max_value * math.sin(2 * math.pi * frequency * index / sample_rate))
        buffer.extend(value.to_bytes(2, byteorder="little", signed=True))
    return bytes(buffer)


def write_wav_file(path: Path, pcm_data: bytes, sample_rate: int) -> None:
    wav_path = path.with_suffix(".wav")
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    print(f"Wrote WAV file: {wav_path}")


def main() -> None:
    args = build_parser().parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pcm_data = generate_pcm_bytes(
        duration=args.duration,
        sample_rate=args.sample_rate,
        frequency=args.frequency,
        amplitude=args.amplitude,
    )
    output_path.write_bytes(pcm_data)

    print(f"Wrote PCM file: {output_path}")
    print(f"Bytes: {len(pcm_data)}")
    print(f"Sample rate: {args.sample_rate}")
    print("Channels: 1")
    print("Format: pcm_s16le")

    if args.wav:
        write_wav_file(output_path, pcm_data, args.sample_rate)


if __name__ == "__main__":
    main()
