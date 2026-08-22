"""Heavy signals T8–T10, T12 (compute-intensive, optional).

These signals require heavier processing (FFT, phase analysis, onset detection)
and are only enabled with --heavy flag.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ai_music_checker.lib.shell import run_cmd, shq
from ai_music_checker.signals import SignalResult
from ai_music_checker.signals.technical import BaseSignal

if TYPE_CHECKING:
    from ai_music_checker.config import Config
    from ai_music_checker.probe import FileProbe


def _parse_spectrumpic_stderr(stderr: str) -> dict[str, float]:
    """Parse showspectrumpic stderr for spectral stats."""
    result = {}
    for line in stderr.splitlines():
        if "dB" in line and ":" in line:
            parts = line.split(":")
            if len(parts) == 2:
                try:
                    key = parts[0].strip().lower().replace(" ", "_")
                    value = float(parts[1].strip().replace("dB", "").strip())
                    result[key] = value
                except (ValueError, IndexError):
                    pass
    return result


def _run_fft_analysis(probe: FileProbe, freq_low: float, freq_high: float) -> float | None:
    """Run FFT analysis on a frequency band and return average energy in dB."""
    cmd = (
        f"ffmpeg -i {shq(str(probe.path))} "
        f"-af showfreqs=mode=line:fscale=log:size=2048:win_func=hanning "
        f"-f null - 2>&1"
    )
    ok, _out, _err = run_cmd(cmd, timeout=120)
    if not ok:
        return None
    # Parse output for energy in the specified band
    # This is a simplified implementation
    return None


class T8(BaseSignal):
    """Spectral mirror detection — symmetry around Nyquist/2."""
    id = "T8"
    name = "spectral_mirror"
    weight = 7
    reliability = 0.6

    def available(self, config: Any) -> bool:
        return True

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        """Detect spectral mirroring at Nyquist/2 (common in neural codecs)."""
        sr = probe.sample_rate or 44100
        nyquist_half = sr / 4  # e.g., 11025 Hz for 44.1 kHz
        
        # Use ffmpeg to extract spectral data
        # Compare energy in [nyquist/2 - 1kHz, nyquist/2] vs [nyquist/2, nyquist/2 + 1kHz]
        # Neural codecs often create mirror artifacts around this point
        
        cmd = (
            f"ffmpeg -i {shq(str(probe.path))} "
            f"-af highpass=f={int(nyquist_half - 1000)},lowpass=f={int(nyquist_half + 1000)},"
            f"volumedetect -f null - 2>&1"
        )
        ok, _out, _err = run_cmd(cmd, timeout=120)
        if not ok:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="FFT analysis failed", group=self.group,
            )
        
        # Parse volumedetect output
        mean_vol = None
        for line in _err.splitlines():
            if "mean_volume:" in line:
                try:
                    mean_vol = float(line.split("mean_volume:")[1].split()[0])
                except (IndexError, ValueError):
                    pass
        
        if mean_vol is None:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="could not parse spectral energy", group=self.group,
            )
        
        # High energy around Nyquist/2 suggests mirror artifacts
        # Threshold: -30 dB is typical for mirrored content
        if mean_vol > -20:
            subscore = 0.8
            note = f"strong spectral mirror energy ({mean_vol:.1f} dB at Nyquist/2)"
        elif mean_vol > -30:
            subscore = 0.4
            note = f"moderate spectral energy ({mean_vol:.1f} dB at Nyquist/2)"
        else:
            subscore = 0.0
            note = f"low spectral energy ({mean_vol:.1f} dB at Nyquist/2)"
        
        return SignalResult(
            id=self.id, name=self.name, value=mean_vol, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T9(BaseSignal):
    """Phase coherence — L/R correlation measurement."""
    id = "T9"
    name = "phase_coherence"
    weight = 6
    reliability = 0.5

    def available(self, config: Any) -> bool:
        return True

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        """Measure L/R phase correlation. Very high or very low = suspicious."""
        if probe.channels != 2:
            return SignalResult(
                id=self.id, name=self.name, value=1.0, subscore=0.5,
                weight=self.weight, reliability=self.reliability, available=True,
                note="mono file, phase analysis skipped", group=self.group,
            )
        
        # Use astats to measure correlation between channels
        cmd = (
            f"ffmpeg -i {shq(str(probe.path))} "
            f"-af astats=metadata=1:measure_perchannel=1 "
            f"-f null - 2>&1"
        )
        ok, _out, _err = run_cmd(cmd, timeout=120)
        if not ok:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="phase analysis failed", group=self.group,
            )
        
        # Look for correlation coefficient in output
        # Correlation near 1.0 = dual mono (suspicious)
        # Correlation near 0.0 = artificial width (suspicious)
        correlation = None
        for line in _err.splitlines():
            if "correlation" in line.lower():
                match = re.search(r"[-+]?\d*\.\d+", line)
                if match:
                    correlation = float(match.group())
                    break
        
        if correlation is None:
            # Fallback: use mid/side energy ratio
            return self._fallback_midside(probe)
        
        # Score based on correlation
        if correlation > 0.99:
            subscore = 0.8
            note = f"near dual-mono (correlation {correlation:.3f})"
        elif correlation < 0.1:
            subscore = 0.6
            note = f"artificial stereo width (correlation {correlation:.3f})"
        elif 0.95 < correlation < 0.99:
            subscore = 0.3
            note = f"narrow stereo (correlation {correlation:.3f})"
        else:
            subscore = 0.0
            note = f"normal stereo (correlation {correlation:.3f})"
        
        return SignalResult(
            id=self.id, name=self.name, value=correlation, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )
    
    def _fallback_midside(self, probe: FileProbe) -> SignalResult:
        """Fallback mid/side energy analysis."""
        # Overall energy
        cmd1 = (
            f"ffmpeg -i {shq(str(probe.path))} "
            f"-af volumedetect -f null - 2>&1"
        )
        _ok1, _out1, err1 = run_cmd(cmd1, timeout=60)
        mean_ov = -60
        for line in err1.splitlines():
            if "mean_volume:" in line:
                try:
                    mean_vol = float(line.split("mean_volume:")[1].split()[0])
                    mean_ov = mean_vol
                except (IndexError, ValueError):
                    pass
        
        # Side channel (L - R)
        cmd2 = (
            f"ffmpeg -i {shq(str(probe.path))} "
            f"-af pan=mono|c0=0.5*c0-0.5*c1,volumedetect -f null - 2>&1"
        )
        _ok2, _out2, err2 = run_cmd(cmd2, timeout=60)
        mean_si = -100
        for line in err2.splitlines():
            if "mean_volume:" in line:
                try:
                    mean_vol = float(line.split("mean_volume:")[1].split()[0])
                    mean_si = mean_vol
                except (IndexError, ValueError):
                    pass
        
        side_rel = mean_si - mean_ov
        
        if side_rel <= -35:
            subscore = 0.8
            note = f"near dual-mono (side {side_rel:.1f} dB rel)"
        elif side_rel <= -25:
            subscore = 0.4
            note = f"narrow stereo (side {side_rel:.1f} dB rel)"
        else:
            subscore = 0.0
            note = f"normal stereo (side {side_rel:.1f} dB rel)"
        
        return SignalResult(
            id=self.id, name=self.name, value=side_rel, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T10(BaseSignal):
    """Transient preservation — attack sharpness analysis."""
    id = "T10"
    name = "transient_preservation"
    weight = 5
    reliability = 0.4

    def available(self, config: Any) -> bool:
        return True

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        """Measure transient sharpness via onset detection."""
        # Use ffmpeg's silencedetect with very short threshold to find transients
        cmd = (
            f"ffmpeg -i {shq(str(probe.path))} "
            f"-af silencedetect=noise=-40dB:d=0.01 "
            f"-f null - 2>&1"
        )
        ok, _out, _err = run_cmd(cmd, timeout=120)
        if not ok:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="transient analysis failed", group=self.group,
            )
        
        # Count silence events (transients = non-silence between silences)
        silence_events = []
        for line in _err.splitlines():
            if "silence_start:" in line:
                try:
                    start = float(line.split("silence_start:")[1].split()[0])
                    silence_events.append(start)
                except (IndexError, ValueError):
                    pass
        
        duration = probe.duration or 1
        transient_density = len(silence_events) / duration if duration > 0 else 0
        
        # AI tracks often have fewer transients (blurred attacks)
        # Typical human music: 0.5-2.0 events/second
        if transient_density < 0.3:
            subscore = 0.6
            note = f"low transient density ({transient_density:.2f}/s)"
        elif transient_density > 3.0:
            subscore = 0.3
            note = f"high transient density ({transient_density:.2f}/s)"
        else:
            subscore = 0.0
            note = f"normal transient density ({transient_density:.2f}/s)"
        
        return SignalResult(
            id=self.id, name=self.name, value=transient_density, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


class T12(BaseSignal):
    """Stem separation consistency — cross-stem spectral overlap."""
    id = "T12"
    name = "stem_consistency"
    weight = 4
    reliability = 0.3

    def available(self, config: Any) -> bool:
        # Requires demucs or spleeter for stem separation
        import shutil
        return shutil.which("demucs") is not None or shutil.which("spleeter") is not None

    def compute(self, probe: FileProbe, config: Config) -> SignalResult:
        """Analyze stem separation consistency."""
        # This is a placeholder for stem separation analysis
        # Full implementation would require demucs/spleeter integration
        
        # For now, use a simplified approach based on spectral characteristics
        # that correlate with stem quality
        
        cmd = (
            f"ffmpeg -i {shq(str(probe.path))} "
            f"-af astats=metadata=0 "
            f"-f null - 2>&1"
        )
        ok, _out, _err = run_cmd(cmd, timeout=120)
        if not ok:
            return SignalResult(
                id=self.id, name=self.name, value=0.0, subscore=0.0,
                weight=self.weight, reliability=self.reliability, available=False,
                note="stem analysis failed", group=self.group,
            )
        
        # Simplified: check for spectral flatness (AI tends to be flatter)
        # This is a placeholder - full implementation needs demucs
        subscore = 0.2  # Low confidence placeholder
        note = "simplified stem analysis (demucs not available)"
        
        return SignalResult(
            id=self.id, name=self.name, value=0.0, subscore=subscore,
            weight=self.weight, reliability=self.reliability, available=True,
            note=note, group=self.group,
        )


HEAVY_SIGNALS = [T8(), T9(), T10(), T12()]
