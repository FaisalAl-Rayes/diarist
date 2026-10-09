export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface JobOptions {
  language: string | null;
  speakers: number | null;
  initial_prompt: string | null;
}

export interface Word {
  start: number;
  end: number;
  text: string;
  speaker?: string;
  probability?: number;
}

export interface Utterance {
  id: number | null;
  start: number;
  end: number;
  speaker: string;
  text: string;
  words: Word[];
}

export interface Transcript {
  schema_version: string;
  source: string;
  language: string;
  requested_language: string | null;
  duration: number;
  models: { transcription: string; diarization: string };
  requested_speakers: number | null;
  speakers: string[];
  utterances: Utterance[];
}

export interface Job {
  id: string;
  original_filename: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  options: JobOptions;
  error: string | null;
  transcript: Transcript | null;
}

export interface Language {
  code: string;
  name: string;
}
