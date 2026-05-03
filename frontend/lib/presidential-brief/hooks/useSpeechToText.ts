"use client";

import { useState, useRef, useCallback, useEffect } from "react";

interface SpeechRecognitionEvent {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface BrowserSpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface BrowserSpeechRecognitionConstructor {
  new (): BrowserSpeechRecognition;
}

export function useSpeechToText() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  /** True after user starts until user explicitly stops — survives `onend` bursts from Chrome/WebKit. */
  const userWantsListeningRef = useRef(false);
  const restartTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRestartTimeout = useCallback(() => {
    if (restartTimeoutRef.current) {
      clearTimeout(restartTimeoutRef.current);
      restartTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => () => clearRestartTimeout(), [clearRestartTimeout]);

  useEffect(() => {
    const browserWindow = window as Window & {
      SpeechRecognition?: BrowserSpeechRecognitionConstructor;
      webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor;
    };
    const SpeechRecognition =
      browserWindow.SpeechRecognition || browserWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    setIsSupported(true);
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";
      let interimTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript += result[0].transcript;
        } else {
          interimTranscript += result[0].transcript;
        }
      }
      setTranscript((prev) => {
        if (finalTranscript) return prev + finalTranscript;
        return (
          prev.replace(/\s*\[.*\]$/, "") +
          (interimTranscript ? ` [${interimTranscript}]` : "")
        );
      });
    };

    recognition.onerror = (event: Event & { error?: string }) => {
      const code = event.error;
      if (code === "aborted") return;
      if (
        code === "not-allowed" ||
        code === "service-not-allowed" ||
        code === "audio-capture"
      ) {
        userWantsListeningRef.current = false;
        clearRestartTimeout();
        setIsListening(false);
      }
    };

    recognition.onend = () => {
      if (!userWantsListeningRef.current) {
        setIsListening(false);
        return;
      }
      clearRestartTimeout();
      restartTimeoutRef.current = setTimeout(() => {
        restartTimeoutRef.current = null;
        const r = recognitionRef.current;
        if (!r || !userWantsListeningRef.current) {
          setIsListening(false);
          return;
        }
        try {
          r.start();
        } catch {
          userWantsListeningRef.current = false;
          setIsListening(false);
        }
      }, 0);
    };

    recognitionRef.current = recognition;

    return () => {
      userWantsListeningRef.current = false;
      clearRestartTimeout();
      try {
        recognition.stop();
      } catch {
        /* noop */
      }
      recognitionRef.current = null;
    };
  }, [clearRestartTimeout]);

  const startListening = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition) return;
    if (userWantsListeningRef.current) return;

    userWantsListeningRef.current = true;
    setTranscript("");
    try {
      recognition.start();
      setIsListening(true);
    } catch {
      userWantsListeningRef.current = false;
      setIsListening(false);
    }
  }, []);

  const stopListening = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition || !userWantsListeningRef.current) return;

    userWantsListeningRef.current = false;
    clearRestartTimeout();
    try {
      recognition.stop();
    } catch {
      /* noop */
    }
    setIsListening(false);
    setTranscript((prev) => prev.replace(/\s*\[.*\]$/, "").trim());
  }, [clearRestartTimeout]);

  const resetTranscript = useCallback(() => {
    setTranscript("");
  }, []);

  return {
    isListening,
    transcript,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
  };
}
