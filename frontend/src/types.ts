export type TutorMode =
  | "guided_reading"
  | "morphology_coach"
  | "translation_support"
  | "oral_reading";

export interface SessionDraft {
  learnerName: string;
  mode: TutorMode;
  targetText: string;
  preferredResponseLanguage: string;
}

export interface ModeSummary {
  value: TutorMode;
  label: string;
  goal: string;
  first_turn: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  notes: string;
  input_schema: Record<string, unknown>;
  status: "placeholder" | "ready";
}

export interface LiveSessionPlan {
  provider: string;
  model: string;
  websocket_path: string;
  protocol_version: string;
  accepted_client_events: string[];
  emitted_server_events: string[];
  input_audio_mime_type: string;
  output_audio_mime_type: string;
  accepted_image_mime_types: string[];
  supports_session_resumption: boolean;
  audio_input: boolean;
  audio_output: boolean;
  image_input: boolean;
  status: "scaffold";
  notes: string;
}

export interface SessionStateSnapshot {
  session_id: string;
  mode: TutorMode;
  step: string;
  target_text: string | null;
  worksheet_attached: boolean;
  microphone_ready: boolean;
  camera_ready: boolean;
  active_focus: string;
}

export interface SessionBootstrapPayload {
  learner_name: string;
  mode: TutorMode;
  target_text: string;
  worksheet_attached: boolean;
  microphone_ready: boolean;
  camera_ready: boolean;
  preferred_response_language: string;
}

export interface SessionBootstrapResponse {
  session_id: string;
  mode: TutorMode;
  mode_label: string;
  mode_goal: string;
  system_prompt_preview: string;
  session_state: SessionStateSnapshot;
  tools: ToolDefinition[];
  live_session: LiveSessionPlan;
  orchestration: {
    engine: string;
    status: string;
    adk_ready: boolean;
    loop: string[];
  };
  next_steps: string[];
}

export interface RuntimeSnapshot {
  service_name: string;
  environment: string;
  google_cloud_project: string | null;
  google_cloud_location: string;
  websocket_path: string;
  live_protocol_version: string;
  default_mode: TutorMode;
  use_google_adk: boolean;
  google_adk_available: boolean;
  google_adk_detail: string;
  google_genai_available: boolean;
  google_genai_detail: string;
  tools: string[];
}
