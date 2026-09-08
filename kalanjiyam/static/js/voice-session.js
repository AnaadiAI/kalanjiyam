/**
 * Microphone capture with silence-based utterance segmentation.
 *
 * Owns the mic and nothing else: it knows about audio levels and time, not
 * about blocks, documents, or the network. Callers get one `onSegment(blob)`
 * per utterance and decide what to do with it.
 *
 * The design problem here is that the mic is *always on*. A push-to-talk button
 * would make segmentation trivial, but it also means a hand stays on the
 * keyboard, which defeats the point. So we watch the signal level and cut a
 * segment when the speaker stops:
 *
 *   silence ──speech starts──> recording ──1.2s of silence──> emit, keep going
 *
 * The noise floor is measured at startup rather than hardcoded. A fixed
 * threshold that works in a quiet office fires continuously in a room with a
 * ceiling fan, and never fires at all on a mic with aggressive gain control.
 */

/** How often we sample the input level, in ms. */
const TICK_MS = 50;

/** Silence needed to close an utterance. Shortened from 1200ms to 850ms to
 *  make responses much snappier after the user stops speaking. */
const SILENCE_MS = 850;

/** Utterances shorter than this are coughs, clicks, and chair scrapes. */
const MIN_SPEECH_MS = 400;

/** Hard cap on one utterance. Someone reading a long passage aloud should
 *  still get incremental results rather than one enormous clip at the end. */
const MAX_SEGMENT_MS = 30000;

/** Sampling window used to establish the noise floor at startup. */
const CALIBRATION_MS = 500;

/** Speech must exceed the noise floor by this factor. Multiplicative rather
 *  than additive so it scales with the room and the mic's gain. */
const SPEECH_FACTOR = 2.5;

/** Absolute floor, so a pathologically silent input (a muted or virtual
 *  device) cannot calibrate to ~0 and then treat its own dither as speech. */
const MIN_THRESHOLD = 0.015;

/** Consecutive loud samples required to reset the silence timer.
 *  Prevents single-tick fan/mic noise spikes on budget PCs from keeping the
 *  utterance open indefinitely. */
const CONSECUTIVE_LOUD_TICKS_RESET = 2;

/** Containers in preference order. Chrome/Firefox take the first, Safari mp4. */
const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
];

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') return '';
  const found = MIME_CANDIDATES.find(
    (t) => typeof MediaRecorder.isTypeSupported === 'function' && MediaRecorder.isTypeSupported(t),
  );
  return found || '';
}

export function isVoiceCaptureSupported() {
  return !!(
    typeof navigator !== 'undefined'
    && navigator.mediaDevices
    && typeof navigator.mediaDevices.getUserMedia === 'function'
    && typeof window !== 'undefined'
    && typeof MediaRecorder !== 'undefined'
    && (window.AudioContext || window.webkitAudioContext)
  );
}

export default class VoiceSession {
  /**
   * @param {object} handlers
   * @param {(blob: Blob) => void} handlers.onSegment  one complete utterance
   * @param {(level: number) => void} [handlers.onLevel]  0..1, for a meter
   * @param {(err: Error) => void} [handlers.onError]
   * @param {(state: string) => void} [handlers.onState] 'calibrating'|'listening'|'speaking'
   */
  constructor({ onSegment, onLevel, onError, onState } = {}) {
    this.onSegment = onSegment || (() => {});
    this.onLevel = onLevel || (() => {});
    this.onError = onError || (() => {});
    this.onState = onState || (() => {});

    this.stream = null;
    this.audioContext = null;
    this.analyser = null;
    this.recorder = null;
    this.timer = null;

    this.chunks = [];
    this.isSpeaking = false;
    this.silenceMs = 0;
    this.speechMs = 0;
    this.consecutiveLoudTicks = 0;
    this.threshold = MIN_THRESHOLD;
    this.calibrationMs = 0;
    this.calibrationPeak = 0;
    this.running = false;
    this.mimeType = '';
  }

  async start() {
    if (this.running) return;
    if (!isVoiceCaptureSupported()) {
      throw new Error('This browser cannot record audio.');
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: { ideal: 1 },
        sampleRate: { ideal: 16000 },
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.audioContext = new Ctx();
    // Chrome starts contexts suspended until a user gesture; the mic toggle is
    // one, but resume() is cheap and makes the ordering explicit.
    if (this.audioContext.state === 'suspended') {
      try { await this.audioContext.resume(); } catch (e) { /* non-fatal */ }
    }
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 1024;
    this.audioContext.createMediaStreamSource(this.stream).connect(this.analyser);

    this.mimeType = pickMimeType();
    this.running = true;
    this.isSpeaking = false;
    this.silenceMs = 0;
    this.speechMs = 0;
    this.calibrationMs = 0;
    this.calibrationPeak = 0;
    this.onState('calibrating');

    const buffer = new Uint8Array(this.analyser.fftSize);
    this.timer = setInterval(() => this._tick(buffer), TICK_MS);
  }

  /** Root-mean-square amplitude of the current window, roughly 0..1. */
  _level(buffer) {
    this.analyser.getByteTimeDomainData(buffer);
    let sum = 0;
    for (let i = 0; i < buffer.length; i += 1) {
      const v = (buffer[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / buffer.length);
  }

  _tick(buffer) {
    if (!this.running || !this.analyser) return;

    const level = this._level(buffer);
    this.onLevel(level);

    // Establish the noise floor before trusting anything. If the user happens
    // to be talking during calibration we land on a high threshold and simply
    // miss the first utterance -- better than a threshold that never resets.
    if (this.calibrationMs < CALIBRATION_MS) {
      this.calibrationMs += TICK_MS;
      this.calibrationPeak = Math.max(this.calibrationPeak, level);
      if (this.calibrationMs >= CALIBRATION_MS) {
        this.threshold = Math.max(MIN_THRESHOLD, this.calibrationPeak * SPEECH_FACTOR);
        this.onState('listening');
      }
      return;
    }

    const loud = level > this.threshold;

    if (!this.isSpeaking) {
      if (loud) {
        this.consecutiveLoudTicks += 1;
        // Require at least 2 consecutive loud ticks (100ms) to begin an utterance,
        // filtering out isolated mic pops, clicks, and fan flutter.
        if (this.consecutiveLoudTicks >= 2) {
          this.consecutiveLoudTicks = 0;
          this._beginUtterance();
        }
      } else {
        this.consecutiveLoudTicks = 0;
      }
      return;
    }

    this.speechMs += TICK_MS;

    if (loud) {
      this.consecutiveLoudTicks += 1;
      // Only reset the silence counter when sound is sustained. Single-tick
      // background spikes (fan whir, breathing, static) will not reset the
      // countdown to 0.
      if (this.consecutiveLoudTicks >= CONSECUTIVE_LOUD_TICKS_RESET) {
        this.silenceMs = 0;
      }
    } else {
      this.consecutiveLoudTicks = 0;
      this.silenceMs += TICK_MS;
    }

    if (this.silenceMs >= SILENCE_MS || this.speechMs >= MAX_SEGMENT_MS) {
      this._endUtterance();
    }
  }

  _beginUtterance() {
    this.isSpeaking = true;
    this.silenceMs = 0;
    this.speechMs = 0;
    this.consecutiveLoudTicks = 0;
    this.chunks = [];
    this.onState('speaking');

    try {
      const opts = {
        ...(this.mimeType ? { mimeType: this.mimeType } : {}),
        audioBitsPerSecond: 24000,
      };
      this.recorder = new MediaRecorder(this.stream, opts);
    } catch (e) {
      try {
        const fallbackOpts = this.mimeType ? { mimeType: this.mimeType } : {};
        this.recorder = new MediaRecorder(this.stream, fallbackOpts);
      } catch (errFallback) {
        this.isSpeaking = false;
        this.onError(errFallback);
        return;
      }
    }

    this.recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) this.chunks.push(e.data);
    };
    this.recorder.onstop = () => {
      const blob = new Blob(this.chunks, { type: this.mimeType || 'audio/webm' });
      this.chunks = [];
      // Re-check duration at stop time: the tick that triggered the stop knows
      // how long we recorded, and anything too brief is not worth a round trip.
      if (this.speechMs - this.silenceMs >= MIN_SPEECH_MS && blob.size > 0) {
        this.onSegment(blob);
      }
      if (this.running) this.onState('listening');
    };

    try {
      this.recorder.start();
    } catch (e) {
      this.isSpeaking = false;
      this.onError(e);
    }
  }

  _endUtterance() {
    this.isSpeaking = false;
    this.consecutiveLoudTicks = 0;
    if (this.recorder && this.recorder.state !== 'inactive') {
      try { this.recorder.stop(); } catch (e) { /* already stopping */ }
    }
    this.recorder = null;
  }

  /**
   * Immediately close and emit the current utterance without waiting
   * for the silence timeout. Safe to call anytime; no-op if not speaking.
   */
  commitUtterance() {
    if (this.isSpeaking) {
      this._endUtterance();
    }
  }

  /** Stop listening but keep the object reusable via start(). */
  stop() {
    if (!this.running) return;
    this.running = false;
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    // Deliberately drop any in-flight utterance: the user asked to stop, so
    // acting on whatever they were half-way through saying would be wrong.
    this.isSpeaking = false;
    this.consecutiveLoudTicks = 0;
    if (this.recorder && this.recorder.state !== 'inactive') {
      this.recorder.onstop = null;
      try { this.recorder.stop(); } catch (e) { /* already stopping */ }
    }
    this.recorder = null;
    this.chunks = [];
    this.onLevel(0);
    this.onState('idle');
  }

  /** Stop and release the microphone. Always call this on teardown --
   *  an un-released track leaves the browser's recording indicator lit. */
  destroy() {
    this.stop();
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.audioContext) {
      try { this.audioContext.close(); } catch (e) { /* already closed */ }
      this.audioContext = null;
    }
    this.analyser = null;
  }
}
