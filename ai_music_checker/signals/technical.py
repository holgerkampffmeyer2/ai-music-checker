"""Technical signals T1–T7 (ffmpeg-driven, local)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ai_music_checker.lib.shell import run_cmd, shq
from ai_music_checker.signals import SignalResult

if TYPE_CHECKING:
    from ai_music_checker.config import Config
    from ai_music_checker.probe import FileProbe


def _criteria_value(config: Any, signal_id: str, field: str) -> Any:
    try:
        return config.criteria[signal_id][field]
    except (AttributeError, KeyError, TypeError):
        from ai_music_checker.config import DEFAULTS

        return DEFAULTS["criteria"].get(signal_id, {}).get(field)


def _parse_volumedetect(stderr: str) -> dict[str, float | None]:
    """Parse mean_volume / max_volume from ffmpeg volumedetect stderr."""
    mean = max_v = None
    for line in stderr.splitlines():
        if "mean_volume:" in line:
            try:
                mean = float(line.split("mean_volume:")[1].split()[0])
            except (IndexError, ValueError):
                pass
        elif "max_volume:" in line:
            try:
                max_v = float(line.split("max_volume:")[1].split()[0])
            except (IndexError, ValueError):
                pass
    return {"mean_volume": mean, "max_volume": max_v}


def _parse_loudnorm_json(stderr: str) -> dict[str, float] | None:
    """Extract the JSON block from loudnorm stderr output."""
    # Find {...} block
    start = stderr.find("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(stderr[start:end + 1])
    except json.JSONDecodeError:
        return None
    _out = {}
    for k in ("input_i", "input_lra", "input_tp", "input_thresh"):
        try:
            _out[k] = float(data.get(k, 0))
        except (TypeError, ValueError):
            _out[k] = 0.0
    return _out


def _parse_astats(stderr: str) -> dict[str, float]:
    """Parse astats Peak/RMS level dB."""
    peak = rms = None
    for line in stderr.splitlines():
        if "Peak level dB:" in line:
            try:
                peak = float(line.split("Peak level dB:")[1].split()[0])
            except (IndexError, ValueError):
                pass
        elif "RMS level dB:" in line:
            try:
                rms = float(line.split("RMS level dB:")[1].split()[0])
            except (IndexError, ValueError):
                pass
    return {"peak_db": peak, "rms_db": rms}


def _parse_silencedetect(stderr: str) -> list[tuple[float, float]]:
    """Parse silencedetect start/end pairs."""
    blocks: list[tuple[float, float]] = []
    start = None
    for line in stderr.splitlines():
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[1].split()[0])
            except (IndexError, ValueError):
                start = None
        elif "silence_end:" in line and start is not None:
            try:
                end = float(line.split("silence_end:")[1].split()[0])
                blocks.append((start, end))
            except (IndexError, ValueError):
                pass
            start = None
    return blocks


class BaseSignal:
    group = "technical"

    def available(self, config: Any) -> bool:
        return True


class T1(BaseSignal):
    """HF energy profile — highpass + volumedetect at threshold & severe."""
    id = "T1"
    name = "hf_energy_profile"
    weight = 12
    reliability = 0.6

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        th_khz = _criteria_value(config, "T1", "threshold_khz") or 16
        sev_khz = _criteria_value(config, "T1", "severe_khz") or 14
        th_hz = int(th_khz * 1000)
        sev_hz = int(sev_khz * 1000)

        cmd = (
            f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
            f"-af highpass=f={th_hz},volumedetect -f null - 2>&1"
        )
        ok, _out, _err = run_cmd(cmd, timeout=60)
        if not ok:
            return SignalResult(id=self.id, name=self.name, value=0.0, subscore=0.5, weight=self.weight, reliability=self.reliability*0.5, available=True, note="ffmpeg failed", group=self.group)
        vol_th = _parse_volumedetect(_out)
        mean_th = vol_th.get("mean_volume")

        if mean_th is None:
            return SignalResult(id=self.id, name=self.name, value=0.0, subscore=0.5, weight=self.weight, reliability=self.reliability*0.5, available=True, note="volumedetect output missing mean_volume", group=self.group)

        # Primary scoring from threshold pass
        if mean_th > -70:
            subscore = 0.0
        elif mean_th <= -90:
            # Check severe pass for hard cutoff distinction
            cmd2 = (
                f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
                f"-af highpass=f={sev_hz},volumedetect -f null - 2>&1"
            )
            _ok2, _out2, _ = run_cmd(cmd2, timeout=60)
            mean_sev = _parse_volumedetect(_out2).get("mean_volume") or -999
            subscore = 1.0 if mean_sev <= -90 else 0.9
        else:
            # Ramp from -70 (0) to -90 (1)
            subscore = min(1.0, max(0.0, (-70 - mean_th) / 20))

        if mean_th > -70:
            note = f"full HF energy above {th_khz} kHz"
        elif mean_th <= -90:
            note = ("hard cutoff below severe threshold" if mean_sev <= -90
                    else f"cutoff between {sev_khz}–{th_khz} kHz")
        else:
            note = f"reduced HF energy ({mean_th:.1f} dB @ {th_khz} kHz)"

        return SignalResult(
            id=self.id, name=self.name, value=mean_th, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T2(BaseSignal):
    """Dynamics / loudness — loudnorm (I, LRA, TP) + astats crest factor."""
    id = "T2"
    name = "dynamics_loudness"
    weight = 8
    reliability = 0.5

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        crest_th = _criteria_value(config, "T2", "crest_db_threshold") or 8
        lra_th = _criteria_value(config, "T2", "lra_lu_threshold") or 3

        # loudnorm pass
        cmd1 = (
            f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
            f"-af loudnorm=print_format=json -f null - 2>&1"
        )
        _ok1, _out1, _ = run_cmd(cmd1, timeout=60)
        if not _ok1:
            raise RuntimeError("T2 loudnorm failed")
        loud = _parse_loudnorm_json(_out1)
        if loud is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="loudnorm JSON unparseable", group=self.group,
            )

        lra = loud.get("input_lra", 99)

        # astats for crest
        cmd2 = (
            f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
            f"-af astats=metadata=0 -f null - 2>&1"
        )
        _ok2, _out2, _ = run_cmd(cmd2, timeout=60)
        if not _ok2:
            raise RuntimeError("T2 astats failed")
        stats = _parse_astats(_out2)
        peak = stats.get("peak_db")
        rms = stats.get("rms_db")
        if peak is None or rms is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="astats missing peak/rms", group=self.group,
            )
        crest = peak - rms  # dB

        # Piecewise scoring
        def clamp01(x: float) -> float:
            return max(0.0, min(1.0, x))

        crest_comp = clamp01((crest_th * 1.5 - crest) / (crest_th * 0.5))  # ≥12→0, <8→1
        lra_comp = clamp01((lra_th * 2 - lra) / lra_th)                    # ≥6→0, <3→1
        subscore = (crest_comp + lra_comp) / 2

        note = f"crest {crest:.1f} dB, LRA {lra:.1f} LU"
        return SignalResult(
            id=self.id, name=self.name, value=lra, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T3(BaseSignal):
    """Stereo anomalies — side-channel energy via mid/side pan."""
    id = "T3"
    name = "stereo_anomalies"
    weight = 4
    reliability = 0.4

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        if probe.channels != 2:
            return SignalResult(
                id=self.id, name=self.name, value=1.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="mono master", group=self.group,
            )

        # Overall
        cmd1 = (
            f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
            f"-af volumedetect -f null - 2>&1"
        )
        _ok1, _out1, _ = run_cmd(cmd1, timeout=60)
        vol_ov = _parse_volumedetect(_out1)
        mean_ov = vol_ov.get("mean_volume") or -60

        # Side channel (L - R) / 2 via pan
        cmd2 = (
            f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
            f"-af pan=mono|c0=0.5*c0-0.5*c1,volumedetect -f null - 2>&1"
        )
        _ok2, _out2, _ = run_cmd(cmd2, timeout=60)
        vol_si = _parse_volumedetect(_out2)
        mean_si = vol_si.get("mean_volume") or -100

        side_rel = mean_si - mean_ov  # negative dB relative

        if side_rel <= -35:
            subscore = 0.9
            note = f"near dual-mono (side {side_rel:.1f} dB rel)"
        elif side_rel <= -25:
            subscore = 0.5
            note = f"narrow stereo (side {side_rel:.1f} dB rel)"
        else:
            subscore = 0.0
            note = f"normal stereo width (side {side_rel:.1f} dB rel)"

        return SignalResult(
            id=self.id, name=self.name, value=side_rel, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T4(BaseSignal):
    """Noise floor, seams, fades — digital silence blocks via silencedetect."""
    id = "T4"
    name = "noise_seams_fades"
    weight = 8
    reliability = 0.5

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        dur = probe.duration or 0
        cmd = (
            f"ffmpeg -v info -i {shq(str(probe.path))} -vn "
            f"-af silencedetect=noise=-50dB:d=0.5 -f null - 2>&1"
        )
        ok, _out, _ = run_cmd(cmd, timeout=60)
        if not ok:
            raise RuntimeError("T4 silencedetect failed")

        blocks = _parse_silencedetect(_out)
        interior = [
            (s, e) for s, e in blocks
            if s > 2.0 and e < max(0, dur - 2.0)
        ]

        n = len(interior)
        if n == 0:
            subscore = 0.0
            note = "no interior silence blocks"
        elif n == 1:
            subscore = 0.4
            note = f"1 interior silence block ({interior[0][1]-interior[0][0]:.1f}s)"
        else:
            total = sum(e - s for s, e in interior)
            subscore = 0.8
            note = f"{n} interior silence blocks (total {total:.1f}s)"

        return SignalResult(
            id=self.id, name=self.name, value=float(n), subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T5(BaseSignal):
    """Encoder chain — generator patterns in encoder tags + missing encoder on lossy."""
    id = "T5"
    name = "encoder_chain"
    weight = 5
    reliability = 0.7

    LOSSY_CODECS: frozenset[str] = frozenset({"mp3", "aac", "ogg", "opus", "m4a", "wma"})

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        patterns = [p.lower() for p in _criteria_value(config, "M1", "patterns") or []]
        encoder_keys = ("encoder", "tsse", "writing_library", "software", "comment")

        tags = {k.lower(): v.lower() for k, v in (probe.tags or {}).items()}
        for key in encoder_keys:
            if key in tags:
                val = tags[key]
                for pat in patterns:
                    if pat in val:
                        return SignalResult(
                            id=self.id, name=self.name, value=1.0, subscore=1.0,
                            weight=self.weight, reliability=self.reliability, available=True,
                            note=f"generator pattern '{pat}' in {key}", group=self.group,
                        )

        # No pattern hit
        if probe.codec in self.LOSSY_CODECS and not any(k in tags for k in encoder_keys):
            return SignalResult(
                id=self.id, name=self.name, value=0.3, subscore=0.3,
                weight=self.weight, reliability=self.reliability, available=True,
                note="lossy codec without encoder tag", group=self.group,
            )

        return SignalResult(
            id=self.id, name=self.name, value=0.0, subscore=0.0,
            weight=self.weight, reliability=self.reliability, available=True,
            note="no generator patterns in encoder tags", group=self.group,
        )


class T6(BaseSignal):
    """Sample-rate artifacts — unusual SR / upsample hints."""
    id = "T6"
    name = "sr_artifacts"
    weight = 5
    reliability = 0.5

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        sr = probe.sample_rate
        codec = probe.codec or ""
        br = probe.bitrate or 0

        if sr not in (44100, 48000):
            return SignalResult(
                id=self.id, name=self.name, value=float(sr), subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note=f"unusual sample rate {sr} Hz", group=self.group,
            )

        if sr == 48000 and codec == "mp3" and br <= 192000:
            return SignalResult(
                id=self.id, name=self.name, value=float(sr), subscore=0.4,
                weight=self.weight, reliability=self.reliability, available=True,
                note=f"48 kHz mp3 at {br//1000} kbps — upsample hint", group=self.group,
            )

        return SignalResult(
            id=self.id, name=self.name, value=float(sr), subscore=0.0,
            weight=self.weight, reliability=self.reliability, available=True,
            note="sample rate normal", group=self.group,
        )


class T7(BaseSignal):
    """BPM/duration sanity — very short/long track durations."""
    id = "T7"
    name = "bpm_duration_sanity"
    weight = 3
    reliability = 0.3

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        dur = probe.duration
        if dur is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="duration unknown", group=self.group,
            )

        if dur < 60:
            subscore = 0.6
            note = f"very short track ({dur:.0f}s)"
        elif dur > 900:
            subscore = 0.3
            note = f"very long track ({dur:.0f}s)"
        else:
            subscore = 0.0
            note = f"normal duration ({dur:.0f}s)"

        return SignalResult(
            id=self.id, name=self.name, value=dur, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


TECHNICAL_SIGNALS = [T1(), T2(), T3(), T4(), T5(), T6(), T7()]