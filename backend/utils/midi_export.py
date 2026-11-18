"""
backend/utils/midi_export.py

Standard MIDI File (SMF Format 1) Exporter for HotChords.
Pure-Python binary MIDI serializer requiring zero external dependencies.

Exports canonical SongTimeline piano arrangements (Intermediate or Beginner) into
multi-track MIDI files:
- Track 0: Conductor track (Tempo, Time Signature, Chord Markers)
- Track 1: Right Hand (Melody & Harmony, MIDI Channel 0)
- Track 2: Left Hand (Bass & Accompaniment, MIDI Channel 1)
"""

from __future__ import annotations

import struct
from typing import List, Dict, Any, Optional


def _encode_vlq(val: int) -> bytes:
    """Encodes an integer into MIDI Variable-Length Quantity (VLQ) bytes."""
    v = max(0, int(val))
    buf = [v & 0x7F]
    v >>= 7
    while v > 0:
        buf.append((v & 0x7F) | 0x80)
        v >>= 7
    buf.reverse()
    return bytes(buf)


def _build_track_chunk(events: List[tuple[int, bytes]]) -> bytes:
    """
    Takes a list of `(abs_tick, raw_midi_event_bytes)`, sorts by tick,
    converts to delta ticks, appends End-Of-Track, and wraps in `MTrk`.
    """
    sorted_ev = sorted(events, key=lambda x: (x[0], 0 if (x[1] and (x[1][0] & 0xF0) == 0x80) else 1))
    body = bytearray()
    prev_tick = 0
    for tick, data in sorted_ev:
        delta = max(0, int(tick) - prev_tick)
        body.extend(_encode_vlq(delta))
        body.extend(data)
        prev_tick = int(tick)

    # End of Track Meta Event (FF 2F 00)
    body.extend(_encode_vlq(0))
    body.extend(b"\xFF\x2F\x00")

    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def export_arrangement_to_midi_bytes(
    notes: List[Dict[str, Any]],
    chords: Optional[List[Dict[str, Any]]] = None,
    tempo: float = 120.0,
    time_sig: str = "4/4",
    title: str = "HotChords Piano Arrangement",
    ticks_per_beat: int = 480,
) -> bytes:
    """
    Serializes a list of HotChords note events and chord markers into a Format 1 `.mid` byte stream.
    """
    bpm = max(30.0, min(260.0, float(tempo or 120.0)))
    us_per_beat = int(round(60_000_000.0 / bpm))

    def _sec_to_tick(sec: float) -> int:
        beats = max(0.0, float(sec)) * (bpm / 60.0)
        return int(round(beats * ticks_per_beat))

    # Track 0: Conductor & Markers
    t0_events: List[tuple[int, bytes]] = []
    title_bytes = title.encode("utf-8", errors="ignore")[:120]
    t0_events.append((0, b"\xFF\x03" + _encode_vlq(len(title_bytes)) + title_bytes))

    # Tempo Meta Event (FF 51 03 tt tt tt)
    t0_events.append((0, b"\xFF\x51\x03" + struct.pack(">I", us_per_beat)[1:]))

    # Time Signature Meta Event (FF 58 04 nn dd cc bb)
    num = 3 if str(time_sig).startswith("3") else 4
    t0_events.append((0, bytes([0xFF, 0x58, 0x04, num, 2, 24, 8])))

    for c in (chords or []):
        c_name = str(c.get("chord", c.get("chordName", "")))
        if not c_name or c_name == "N":
            continue
        c_time = float(c.get("time", c.get("startTime", 0.0)))
        c_bytes = c_name.encode("ascii", errors="ignore")[:32]
        if c_bytes:
            t0_events.append((_sec_to_tick(c_time), b"\xFF\x06" + _encode_vlq(len(c_bytes)) + c_bytes))

    # Track 1: Right Hand (Channel 0, Acoustic Grand Piano Program 0)
    rh_events: List[tuple[int, bytes]] = [
        (0, b"\xFF\x03" + _encode_vlq(10) + b"Right Hand"),
        (0, bytes([0xC0, 0x00])),
    ]

    # Track 2: Left Hand (Channel 1, Acoustic Grand Piano Program 0)
    lh_events: List[tuple[int, bytes]] = [
        (0, b"\xFF\x03" + _encode_vlq(9) + b"Left Hand"),
        (0, bytes([0xC1, 0x00])),
    ]

    for n in (notes or []):
        midi = int(max(21, min(108, int(n.get("midi", 60)))))
        vel = int(max(1, min(127, int(n.get("velocity", 80)))))
        start_tick = _sec_to_tick(float(n.get("start", n.get("startTime", 0.0))))
        end_tick = max(start_tick + 20, _sec_to_tick(float(n.get("end", n.get("endTime", 0.2)))))
        hand = str(n.get("hand", "right")).lower()

        if hand == "left":
            lh_events.append((start_tick, bytes([0x91, midi, vel])))
            lh_events.append((end_tick, bytes([0x81, midi, 0])))
        else:
            rh_events.append((start_tick, bytes([0x90, midi, vel])))
            rh_events.append((end_tick, bytes([0x80, midi, 0])))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, 3, ticks_per_beat)
    return (
        header
        + _build_track_chunk(t0_events)
        + _build_track_chunk(rh_events)
        + _build_track_chunk(lh_events)
    )
