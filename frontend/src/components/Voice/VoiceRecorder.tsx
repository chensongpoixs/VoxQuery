'use client';

import { useState, useRef, useEffect } from 'react';

interface VoiceRecorderProps {
  onResult: (audioBlob: Blob) => void;
  onCancel: () => void;
}

export default function VoiceRecorder({ onResult, onCancel }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop();
      }
    };
  }, [isRecording]);

  const startRecording = async () => {
    try {
      setError('');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/wav',
      });

      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach((t) => t.stop());
        if (blob.size > 0) {
          onResult(blob);
        }
      };

      recorder.start(100); // 每 100ms 收集一次数据
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setDuration(0);

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);
    } catch (err) {
      setError('无法访问麦克风，请检查权限设置');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center gap-3">
      {isRecording ? (
        <>
          <div className="flex items-center gap-2 flex-1">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-red-500 text-sm font-medium">录音中</span>
            <span className="text-gray-400 text-sm">{formatTime(duration)}</span>
            {/* 波形动画 */}
            <div className="flex gap-0.5 items-end h-6 ml-2">
              {[3, 6, 4, 8, 5, 7, 4, 6, 5, 8, 4, 7, 5, 6].map((h, i) => (
                <span
                  key={i}
                  className="w-0.5 bg-red-400 rounded-full animate-pulse"
                  style={{
                    height: `${h * 2}px`,
                    animationDelay: `${i * 0.1}s`,
                  }}
                />
              ))}
            </div>
          </div>
          <button
            onClick={stopRecording}
            className="px-4 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600 text-sm"
          >
            停止
          </button>
        </>
      ) : (
        <>
          <button
            onClick={startRecording}
            className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700
                       transition-colors text-sm flex items-center justify-center gap-2"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
              <path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8" />
            </svg>
            点击开始录音
          </button>
        </>
      )}
      <button
        onClick={onCancel}
        className="px-3 py-3 text-gray-400 hover:text-gray-600 rounded-xl hover:bg-gray-100"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
