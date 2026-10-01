import { useState, useEffect, useCallback, useRef } from 'react';
import { wsClient } from '../services/websocket';

export interface UseVoiceEngineOptions {
  autoSpeak?: boolean;
  onBargeIn?: () => void;
  onSpeechRecognized?: (transcript: string) => void;
}

export interface UseVoiceEngineReturn {
  isListening: boolean;
  isSpeaking: boolean;
  isBargeInActive: boolean;
  audioLevel: number;
  currentSentence: string | null;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => void;
  toggleListening: () => Promise<void>;
  triggerBargeIn: () => void;
  speakSentence: (text: string, audioBase64?: string) => void;
  flushAudioQueue: () => void;
}

export function useVoiceEngine(options: UseVoiceEngineOptions = {}): UseVoiceEngineReturn {
  const { autoSpeak = true, onBargeIn, onSpeechRecognized } = options;

  const [isListening, setIsListening] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [isBargeInActive, setIsBargeInActive] = useState<boolean>(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [currentSentence, setCurrentSentence] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const recognitionRef = useRef<any>(null);
  const speechQueueRef = useRef<{ text: string; audioBase64?: string }[]>([]);
  const isPlayingTtsRef = useRef<boolean>(false);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);

  // Flush any pending audio synthesis immediately
  const flushAudioQueue = useCallback(() => {
    speechQueueRef.current = [];
    isPlayingTtsRef.current = false;
    setIsSpeaking(false);
    setCurrentSentence(null);
    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.pause();
        activeAudioRef.current.currentTime = 0;
      } catch {
        // ignore
      }
      activeAudioRef.current = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Ignore synthesis abort errors
      }
    }
  }, []);

  // Instant Barge-In Interruption (<100ms)
  const triggerBargeIn = useCallback(() => {
    flushAudioQueue();
    setIsBargeInActive(true);
    setTimeout(() => setIsBargeInActive(false), 800);

    // Notify backend WebSocket of barge-in
    wsClient.send({
      type: 'voice:barge_in',
      action: 'flush_audio_queue',
      timestamp: Date.now(),
    });

    if (onBargeIn) {
      onBargeIn();
    }
  }, [flushAudioQueue, onBargeIn]);

  // Process next sentence in TTS synthesis queue
  const processNextSentence = useCallback(() => {
    if (speechQueueRef.current.length === 0) {
      isPlayingTtsRef.current = false;
      setIsSpeaking(false);
      setCurrentSentence(null);
      setAudioLevel(0);
      return;
    }

    const nextItem = speechQueueRef.current.shift();
    if (!nextItem) {
      processNextSentence();
      return;
    }

    const nextText = typeof nextItem === 'string' ? nextItem : nextItem.text;
    const audioB64 = typeof nextItem === 'object' ? nextItem.audioBase64 : undefined;

    if (!nextText || !nextText.trim()) {
      processNextSentence();
      return;
    }

    isPlayingTtsRef.current = true;
    setIsSpeaking(true);
    setCurrentSentence(nextText);

    // If neural base64 audio is present, play it directly with lipsync energy
    if (audioB64) {
      try {
        const audio = new Audio(`data:audio/mp3;base64,${audioB64}`);
        activeAudioRef.current = audio;

        // Drive dynamic lipsync audioLevel while playing
        const pulseInterval = setInterval(() => {
          if (!activeAudioRef.current || activeAudioRef.current.paused) {
            clearInterval(pulseInterval);
            return;
          }
          setAudioLevel(0.25 + Math.random() * 0.45);
        }, 120);

        audio.onended = () => {
          clearInterval(pulseInterval);
          activeAudioRef.current = null;
          setAudioLevel(0);
          processNextSentence();
        };

        audio.onerror = () => {
          clearInterval(pulseInterval);
          activeAudioRef.current = null;
          setAudioLevel(0);
          processNextSentence();
        };

        audio.play().catch(() => {
          clearInterval(pulseInterval);
          activeAudioRef.current = null;
          setAudioLevel(0);
          processNextSentence();
        });
        return;
      } catch {
        // Fallback to speech synthesis
      }
    }

    // Fallback: browser speech synthesis
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        const utterance = new SpeechSynthesisUtterance(nextText.trim());
        utterance.rate = 1.08;
        utterance.pitch = 1.25;

        utterance.onend = () => {
          processNextSentence();
        };

        utterance.onerror = () => {
          processNextSentence();
        };

        window.speechSynthesis.speak(utterance);
      } catch {
        processNextSentence();
      }
    } else {
      processNextSentence();
    }
  }, []);

  // Speak a sentence chunk
  const speakSentence = useCallback(
    (text: string, audioBase64?: string) => {
      if (!text || !text.trim()) return;
      speechQueueRef.current.push({ text, audioBase64 });
      if (!isPlayingTtsRef.current) {
        processNextSentence();
      }
    },
    [processNextSentence]
  );

  // Stop listening and release microphone
  const stopListening = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try {
        audioContextRef.current.close();
      } catch {
        // Ignore close errors
      }
      audioContextRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore stop errors
      }
      recognitionRef.current = null;
    }

    setIsListening(false);
    setAudioLevel(0);
  }, []);

  // Start microphone capture & real-time VAD / Speech recognition
  const startListening = useCallback(async () => {
    setError(null);
    try {
      if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
        throw new Error('Microphone access is not supported in this browser.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // Audio analysis for real-time visual waveform / energy
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      audioContextRef.current = audioCtx;

      const sourceNode = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      sourceNode.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateVolume = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length / 255;
        setAudioLevel(avg);

        // Client-side instant barge-in trigger if user speaks during assistant TTS playback
        if (avg > 0.08 && isPlayingTtsRef.current) {
          triggerBargeIn();
        }

        animFrameRef.current = requestAnimationFrame(updateVolume);
      };
      updateVolume();

      // Browser Speech Recognition (if available)
      const SpeechRecognition =
        (window as unknown as { SpeechRecognition?: any; webkitSpeechRecognition?: any }).SpeechRecognition ||
        (window as unknown as { SpeechRecognition?: any; webkitSpeechRecognition?: any }).webkitSpeechRecognition;

      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onresult = (event: any) => {
          const lastIdx = event.results.length - 1;
          const transcript = event.results[lastIdx][0].transcript.trim();
          if (transcript) {
            if (isPlayingTtsRef.current) {
              triggerBargeIn();
            }
            if (onSpeechRecognized) {
              onSpeechRecognized(transcript);
            }
          }
        };

        recognition.onerror = (event: any) => {
          if (event.error !== 'no-speech') {
            setError(`Speech recognition error: ${event.error}`);
          }
        };

        recognition.start();
        recognitionRef.current = recognition;
      }

      setIsListening(true);
    } catch (err: any) {
      setError(err?.message || 'Failed to access microphone.');
      setIsListening(false);
    }
  }, [onSpeechRecognized, triggerBargeIn]);

  const toggleListening = useCallback(async () => {
    if (isListening) {
      stopListening();
    } else {
      await startListening();
    }
  }, [isListening, startListening, stopListening]);

  // Subscribe to WebSocket streaming TTS chunks and barge-in events
  useEffect(() => {
    const unsubTts = wsClient.on('voice:tts_chunk', (data: any) => {
      if (autoSpeak && data?.sentence) {
        speakSentence(data.sentence, data?.audio_base64);
      }
    });

    const unsubBargeIn = wsClient.on('voice:barge_in', () => {
      flushAudioQueue();
    });

    const unsubCancel = wsClient.on('chat:cancel_ack', () => {
      flushAudioQueue();
    });

    return () => {
      unsubTts();
      unsubBargeIn();
      unsubCancel();
    };
  }, [autoSpeak, flushAudioQueue, speakSentence]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopListening();
      flushAudioQueue();
    };
  }, [flushAudioQueue, stopListening]);

  return {
    isListening,
    isSpeaking,
    isBargeInActive,
    audioLevel,
    currentSentence,
    error,
    startListening,
    stopListening,
    toggleListening,
    triggerBargeIn,
    speakSentence,
    flushAudioQueue,
  };
}
