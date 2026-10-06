#!/usr/bin/env python3
"""Audio durations with the Python standard library only (no ffprobe, no third-party packages).

- MP3: Xing/Info or VBRI header frame count, otherwise a walk over every MPEG frame.
- MP4/M4A/AAC-in-MP4: moov/mvhd duration / timescale.
- WAV: wave module.
Shared by build_audio_inventory.py and generate_public_music_data.py.
"""

import struct
import wave

_MP3_BITRATES = {
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_MP3_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _mp3_header(data, pos):
    """Parse an MPEG audio frame header at pos; return a dict or None."""
    if pos + 4 > len(data) or data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
        return None
    version = (data[pos + 1] >> 3) & 3  # 0: 2.5, 2: 2, 3: 1
    layer = (data[pos + 1] >> 1) & 3  # 1: III, 2: II, 3: I
    bitrate_index = data[pos + 2] >> 4
    rate_index = (data[pos + 2] >> 2) & 3
    if version == 1 or layer == 0 or bitrate_index in (0, 15) or rate_index == 3:
        return None
    table = (3 if version == 3 else 2, layer)
    bitrate = _MP3_BITRATES[table][bitrate_index] * 1000
    rate = _MP3_RATES[version][rate_index]
    padding = (data[pos + 2] >> 1) & 1
    mono = (data[pos + 3] >> 6) == 3
    if layer == 3:
        samples, length = 384, (12 * bitrate // rate + padding) * 4
    elif layer == 2 or version == 3:
        samples, length = 1152, 144 * bitrate // rate + padding
    else:
        samples, length = 576, 72 * bitrate // rate + padding
    side = (17 if mono else 32) if version == 3 else (9 if mono else 17)
    return {"rate": rate, "samples": samples, "length": length, "side": side}


def mp3_duration(path, strict=False):
    """Duration of an MP3 file in seconds and the method used.

    Default: trust a Xing/Info/VBRI frame count when present (fast inventory of masters).
    strict=True (public previews): audio must start right after the ID3v2 tags and every MPEG
    frame is walked, so a header that under-reports the length (e.g. concatenated files)
    cannot hide a longer file; trailing bytes other than an ID3v1 tag are rejected.
    """
    data = path.read_bytes()
    pos = 0
    while data[pos:pos + 3] == b"ID3" and pos + 10 <= len(data):
        size = 0
        for byte in data[pos + 6:pos + 10]:
            size = (size << 7) | (byte & 0x7F)
        pos += 10 + size + (10 if data[pos + 5] & 0x10 else 0)
    audio_start = pos
    # First frame confirmed by the following frame header (avoids false sync bytes).
    while pos < len(data) - 4:
        header = _mp3_header(data, pos)
        if header and header["length"] > 0 and _mp3_header(data, pos + header["length"]):
            break
        if strict:
            raise ValueError("audio does not start with two consecutive MPEG frames")
        pos += 1
    else:
        raise ValueError("no MPEG audio frame found")
    if not strict:
        for offset, tag in ((4 + header["side"], (b"Xing", b"Info")), (4 + 32, (b"VBRI",))):
            start = pos + offset
            if data[start:start + 4] in tag:
                if tag[0] == b"VBRI":
                    frames = struct.unpack(">I", data[start + 14:start + 18])[0]
                else:
                    flags = struct.unpack(">I", data[start + 4:start + 8])[0]
                    if not flags & 1:
                        continue
                    frames = struct.unpack(">I", data[start + 8:start + 12])[0]
                method = "mp3 " + tag[0].decode() + " header (frames x samples / rate)"
                return frames * header["samples"] / header["rate"], method
    samples, rate = 0, header["rate"]
    while True:
        frame = _mp3_header(data, pos)
        if not frame or frame["length"] <= 0 or pos + frame["length"] > len(data):
            break
        if strict and frame["rate"] != rate:
            raise ValueError("sample rate changes between frames")
        samples += frame["samples"]
        pos += frame["length"]
    if strict:
        rest = data[pos:]
        if rest and not (len(rest) == 128 and rest[:3] == b"TAG"):
            raise ValueError(f"{len(rest)} unexpected bytes after the last MPEG frame")
        if pos <= audio_start:
            raise ValueError("no MPEG audio frame found")
    return samples / rate, "mp3 frame walk (sum of frame samples / rate)"


def _atoms(data, start, end):
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        header = 8
        if size == 1:
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:
            return
        yield kind, pos + header, pos + size
        pos += size


def mp4_duration(path):
    data = path.read_bytes()
    for kind, start, end in _atoms(data, 0, len(data)):
        if kind != b"moov":
            continue
        for child, cstart, _ in _atoms(data, start, end):
            if child == b"mvhd":
                version = data[cstart]
                if version == 1:
                    timescale, duration = struct.unpack(">IQ", data[cstart + 20:cstart + 32])
                else:
                    timescale, duration = struct.unpack(">II", data[cstart + 12:cstart + 20])
                return duration / timescale, "mp4 moov/mvhd (duration / timescale)"
    raise ValueError("no moov/mvhd atom")


def wav_duration(path):
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate(), "wave module (frames / rate)"


def stdlib_duration(path):
    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            return mp3_duration(path)
        if suffix in (".m4a", ".mp4", ".aac"):
            return mp4_duration(path)
        if suffix == ".wav":
            return wav_duration(path)
    except (ValueError, struct.error, wave.Error, EOFError) as exc:
        return None, f"not readable with the standard library: {exc}"
    return None, f"no standard-library reader for {suffix}"
