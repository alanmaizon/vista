export const LIVE_PROTOCOL_VERSION = "2026-03-15";
export const INPUT_AUDIO_MIME_TYPE = "audio/pcm;rate=16000";
export const OUTPUT_AUDIO_MIME_TYPE = "audio/pcm;rate=24000";

export type ClientEventType =
  | "client.hello"
  | "client.input.text"
  | "client.input.audio"
  | "client.input.image"
  | "client.turn.end"
  | "client.control.interrupt"
  | "client.control.ping";

export type ServerEventType =
  | "server.ready"
  | "server.status"
  | "server.transcript"
  | "server.output.text"
  | "server.output.audio"
  | "server.tool.call"
  | "server.tool.result"
  | "server.turn"
  | "server.session.update"
  | "server.error";

export interface LiveEventBase {
  type: string;
  protocol_version: typeof LIVE_PROTOCOL_VERSION;
}

export interface ClientCapabilities {
  audio_input: boolean;
  audio_output: boolean;
  image_input: boolean;
  supports_barge_in: boolean;
}

export interface ClientHelloEvent extends LiveEventBase {
  type: "client.hello";
  session_id?: string;
  mode?: string;
  target_text?: string;
  preferred_response_language?: string;
  capabilities: ClientCapabilities;
  client_name: string;
}

export interface ClientTextInputEvent extends LiveEventBase {
  type: "client.input.text";
  turn_id: string;
  text: string;
  source: "typed" | "ocr" | "transcript_correction";
  is_final: boolean;
}

export interface ClientAudioInputEvent extends LiveEventBase {
  type: "client.input.audio";
  turn_id: string;
  chunk_index: number;
  mime_type: string;
  data_base64: string;
  is_final_chunk: boolean;
}

export interface ClientImageInputEvent extends LiveEventBase {
  type: "client.input.image";
  turn_id: string;
  frame_index: number;
  mime_type: "image/jpeg" | "image/png" | "image/webp";
  source: "camera_frame" | "worksheet_upload";
  data_base64: string;
  width?: number;
  height?: number;
  is_reference: boolean;
}

export interface ClientTurnEndEvent extends LiveEventBase {
  type: "client.turn.end";
  turn_id: string;
  reason: "done" | "silence_timeout" | "submit_click" | "stop_recording";
}

export interface ClientInterruptEvent extends LiveEventBase {
  type: "client.control.interrupt";
  turn_id?: string;
  reason: "barge_in" | "stop_button" | "navigation" | "connection_reset";
}

export interface ClientPingEvent extends LiveEventBase {
  type: "client.control.ping";
  client_time?: string;
}

export type LiveClientEvent =
  | ClientHelloEvent
  | ClientTextInputEvent
  | ClientAudioInputEvent
  | ClientImageInputEvent
  | ClientTurnEndEvent
  | ClientInterruptEvent
  | ClientPingEvent;

export interface ServerReadyEvent extends LiveEventBase {
  type: "server.ready";
  connection_id: string;
  websocket_path: string;
  accepted_client_events: ClientEventType[];
  emitted_server_events: ServerEventType[];
  input_audio_mime_type: string;
  output_audio_mime_type: string;
  accepted_image_mime_types: Array<"image/jpeg" | "image/png" | "image/webp">;
  supports_session_resumption: boolean;
  notes: string;
}

export interface ServerStatusEvent extends LiveEventBase {
  type: "server.status";
  phase:
    | "ready"
    | "listening"
    | "receiving_input"
    | "thinking"
    | "tool_running"
    | "speaking"
    | "interrupted"
    | "closing"
    | "closed"
    | "error";
  detail: string;
  session_id?: string;
  turn_id?: string;
  resumable?: boolean;
}

export interface ServerTranscriptEvent extends LiveEventBase {
  type: "server.transcript";
  session_id: string;
  turn_id: string;
  speaker: "learner" | "tutor";
  source: "input_text" | "input_audio" | "output_text" | "output_audio_transcription";
  text: string;
  is_final: boolean;
  interrupted: boolean;
}

export interface ServerTextOutputEvent extends LiveEventBase {
  type: "server.output.text";
  session_id: string;
  turn_id: string;
  text: string;
  is_final: boolean;
}

export interface ServerAudioOutputEvent extends LiveEventBase {
  type: "server.output.audio";
  session_id: string;
  turn_id: string;
  chunk_index: number;
  mime_type: string;
  data_base64: string;
  is_final_chunk: boolean;
}

export interface ServerToolCallEvent extends LiveEventBase {
  type: "server.tool.call";
  session_id: string;
  turn_id: string;
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: "requested" | "started";
}

export interface ServerToolResultEvent extends LiveEventBase {
  type: "server.tool.result";
  session_id: string;
  turn_id: string;
  tool_call_id: string;
  tool_name: string;
  status: "completed" | "failed";
  result?: Record<string, unknown> | null;
  error?: string | null;
}

export interface ServerTurnEvent extends LiveEventBase {
  type: "server.turn";
  session_id: string;
  turn_id: string;
  event: "learner_turn_closed" | "generation_complete" | "turn_complete" | "interrupted";
  detail?: string;
}

export interface ServerSessionUpdateEvent extends LiveEventBase {
  type: "server.session.update";
  session_id?: string;
  resumption_handle?: string;
  go_away: boolean;
  time_left_ms?: number;
  context_window_compression?: boolean;
}

export interface ServerErrorEvent extends LiveEventBase {
  type: "server.error";
  code: string;
  message: string;
  retryable: boolean;
  session_id?: string;
  detail: Record<string, unknown>;
}

export type LiveServerEvent =
  | ServerReadyEvent
  | ServerStatusEvent
  | ServerTranscriptEvent
  | ServerTextOutputEvent
  | ServerAudioOutputEvent
  | ServerToolCallEvent
  | ServerToolResultEvent
  | ServerTurnEvent
  | ServerSessionUpdateEvent
  | ServerErrorEvent;
