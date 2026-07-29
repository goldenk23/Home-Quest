import { config } from '../utils/env';
import { MAX_VASTU_FILE_BYTES } from '../store/persistence/importVastu';

export interface FloorPlanMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface GenerateFloorPlanRequest {
  messages: FloorPlanMessage[];
  previousLayout?: unknown;
  signal?: AbortSignal;
}

export interface GenerateFloorPlanResponse {
  layout: unknown;
  assistantMessage: string;
  attempts: number;
}

const endpoint = `${config.apiUrl.replace(/\/$/, '')}/api/floor-plans/generate`;

export async function generateFloorPlan(request: GenerateFloorPlanRequest): Promise<GenerateFloorPlanResponse> {
  const body = JSON.stringify({ messages: request.messages, previousLayout: request.previousLayout });
  if (new TextEncoder().encode(body).byteLength > MAX_VASTU_FILE_BYTES) {
    throw new Error('The refinement context is too large. Start a new AI design session.');
  }
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    signal: request.signal,
  });
  const declaredSize = Number(response.headers.get('content-length') || 0);
  if (declaredSize > MAX_VASTU_FILE_BYTES) throw new Error('AI response is too large.');
  const raw = await response.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_VASTU_FILE_BYTES) throw new Error('AI response is too large.');
  let payload: unknown;
  try { payload = JSON.parse(raw); } catch { throw new Error('AI server returned invalid JSON.'); }
  if (!response.ok) {
    const error = payload && typeof payload === 'object' && 'error' in payload ? String(payload.error) : `AI request failed (${response.status})`;
    throw new Error(error);
  }
  if (!payload || typeof payload !== 'object' || !('layout' in payload) ||
      typeof (payload as { assistantMessage?: unknown }).assistantMessage !== 'string') {
    throw new Error('AI server returned an invalid floor-plan response.');
  }
  return payload as GenerateFloorPlanResponse;
}
