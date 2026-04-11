import { useState, useCallback } from "react";
import { API_BASE } from "../lib/api";
import {
  TriageRequest,
  SSEEventType,
  SSESessionPayload,
  SSEStageStartedPayload,
  SSEStageCompletedPayload,
  SSECompletePayload,
  SSEErrorPayload,
} from "../types/triage";

export interface StreamHandlers {
  onSession: (data: SSESessionPayload) => void;
  onStageStarted: (data: SSEStageStartedPayload) => void;
  onStageCompleted: (data: SSEStageCompletedPayload) => void;
  onComplete: (data: SSECompletePayload) => void;
  onError: (data: SSEErrorPayload | Error) => void;
}

function getStreamError(error: unknown): Error {
  if (error instanceof Error) {
    return error;
  }
  return new Error(String(error));
}

export function useTriageStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const startStream = useCallback(async (request: TriageRequest, handlers: StreamHandlers) => {
    setIsStreaming(true);
    const controller = new AbortController();
    setAbortController(controller);

    try {
      const response = await fetch(`${API_BASE}/api/v1/triage/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status} Failed to start stream`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";

        for (const chunk of chunks) {
          const eventMatch = chunk.match(/^event:\s*(.+)$/m);
          const dataMatch = chunk.match(/^data:\s*(.+)$/m);
          
          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1].trim() as SSEEventType;
          let data: unknown;
          try {
            data = JSON.parse(dataMatch[1]);
          } catch {
            console.error("Invalid JSON in SSE data block", dataMatch[1]);
            continue;
          }

          switch (eventType) {
            case "session":
              handlers.onSession(data as SSESessionPayload);
              break;
            case "stage_started":
              handlers.onStageStarted(data as SSEStageStartedPayload);
              break;
            case "stage_completed":
              handlers.onStageCompleted(data as SSEStageCompletedPayload);
              break;
            case "complete":
              handlers.onComplete(data as SSECompletePayload);
              setIsStreaming(false);
              break;
            case "error":
              handlers.onError(data as SSEErrorPayload);
              setIsStreaming(false);
              break;
          }
        }
      }
    } catch (err: unknown) {
      const streamError = getStreamError(err);
      if (streamError.name === "AbortError") {
        console.log("Stream aborted by user");
      } else {
        handlers.onError(streamError);
      }
      setIsStreaming(false);
    } finally {
      setIsStreaming(false);
      setAbortController(null);
    }
  }, []);

  const stopStream = useCallback(() => {
    if (abortController) {
      abortController.abort();
    }
  }, [abortController]);

  return { isStreaming, startStream, stopStream };
}
