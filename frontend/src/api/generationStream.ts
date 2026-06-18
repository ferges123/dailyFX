import { getApiUrl, getAuthToken } from './client';

export type GenerationStreamConnectionState =
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

export type GenerationStreamEvent = {
  id: number | null;
  event:
    | 'history-upsert'
    | 'task-upsert'
    | 'heartbeat'
    | 'resync-required'
    | string;
  data: unknown;
};

type OpenGenerationStreamOptions = {
  lastEventId?: number;
  onEvent: (event: GenerationStreamEvent) => void;
  onStatus: (status: GenerationStreamConnectionState) => void;
  onResyncRequired: () => void;
};

type ParsedSseEvent = {
  id: number | null;
  event: string;
  data: string;
};

function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function parseSseData(raw: string): unknown {
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function buildEventMessage(event: ParsedSseEvent): GenerationStreamEvent {
  return {
    id: event.id,
    event: event.event,
    data: parseSseData(event.data),
  };
}

async function consumeEventStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  onDispatch: (event: GenerationStreamEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let current: ParsedSseEvent = { id: null, event: 'message', data: '' };

  const dispatchCurrent = () => {
    if (
      current.event === 'message' &&
      current.data.length === 0 &&
      current.id === null
    )
      return;
    onDispatch(buildEventMessage(current));
    current = { id: null, event: 'message', data: '' };
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        if (buffer.length > 0) {
          buffer += decoder.decode();
        }
        if (
          current.event !== 'message' ||
          current.data.length > 0 ||
          current.id !== null
        ) {
          dispatchCurrent();
        }
        return;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (signal.aborted) return;
        if (!line) {
          dispatchCurrent();
          continue;
        }
        if (line.startsWith(':')) continue;
        const colonIndex = line.indexOf(':');
        const field = colonIndex >= 0 ? line.slice(0, colonIndex) : line;
        let rawValue = colonIndex >= 0 ? line.slice(colonIndex + 1) : '';
        if (rawValue.startsWith(' ')) {
          rawValue = rawValue.slice(1);
        }

        if (field === 'id') {
          const parsed = Number.parseInt(rawValue, 10);
          current.id = Number.isFinite(parsed) ? parsed : null;
        } else if (field === 'event') {
          current.event = rawValue || 'message';
        } else if (field === 'data') {
          current.data = current.data
            ? `${current.data}\n${rawValue}`
            : rawValue;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function openGenerationStream(options: OpenGenerationStreamOptions): {
  close: () => void;
} {
  const controller = new AbortController();
  let closed = false;
  let lastEventId = options.lastEventId ?? 0;
  let attempt = 0;

  const stop = () => {
    if (closed) return;
    closed = true;
    controller.abort();
    options.onStatus('disconnected');
  };

  const run = async () => {
    options.onStatus('reconnecting');

    while (!closed) {
      try {
        const headers = new Headers({
          Accept: 'text/event-stream',
          ...getAuthHeaders(),
        });
        if (lastEventId > 0) {
          headers.set('Last-Event-ID', String(lastEventId));
        }

        const response = await fetch(getApiUrl('/api/generation/stream'), {
          method: 'GET',
          headers,
          signal: controller.signal,
        });

        if (response.status === 401 || response.status === 403) {
          stop();
          return;
        }

        if (!response.ok || !response.body) {
          throw new Error(`SSE request failed with ${response.status}`);
        }

        options.onStatus('connected');

        await consumeEventStream(response.body, controller.signal, (event) => {
          if (closed) return;
          if (typeof event.id === 'number' && Number.isFinite(event.id)) {
            lastEventId = event.id;
          }

          if (event.event === 'resync-required') {
            stop();
            options.onEvent(event);
            options.onResyncRequired();
            return;
          }

          options.onEvent(event);
        });

        if (closed) return;
        options.onStatus('reconnecting');
        attempt += 1;
        const delayMs = Math.min(10_000, 1000 * Math.max(1, attempt));
        await sleep(delayMs);
      } catch {
        if (closed || controller.signal.aborted) {
          return;
        }

        attempt += 1;
        options.onStatus('reconnecting');
        const delayMs = Math.min(10_000, 1000 * Math.max(1, attempt));
        await sleep(delayMs);
      }
    }
  };

  void run();

  return { close: stop };
}
