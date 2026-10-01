/**
 * NIKO AI Character & Embodiment Type Definitions
 * 
 * Implements authoritative visual & behavioral states defined in:
 * - Master Character Sheet
 * - Personality Sheet
 * - AI-First Embodiment Architecture
 */

export type AssistantSemanticState =
  | 'ASSISTANT_IDLE'
  | 'ASSISTANT_LISTENING'
  | 'ASSISTANT_THINKING'
  | 'ASSISTANT_PROCESSING'
  | 'ASSISTANT_SPEAKING'
  | 'ASSISTANT_WORKING'
  | 'ASSISTANT_WAITING'
  | 'ASSISTANT_SUCCESS'
  | 'ASSISTANT_ERROR'
  | 'ASSISTANT_NEEDS_PERMISSION'
  | 'ASSISTANT_COOLING_DOWN';

export type CharacterPosture =
  | 'STANDING'
  | 'WALKING'
  | 'SITTING'
  | 'LYING'
  | 'SLEEPING'
  | 'JUMPING'
  | 'DRAGGED';

export type CharacterEmotion =
  | 'NEUTRAL'
  | 'HAPPY'
  | 'EXCITED'
  | 'SAD'
  | 'ANGRY'
  | 'SURPRISED'
  | 'CURIOUS'
  | 'CONFUSED'
  | 'SLEEPY'
  | 'BORED';

export type EnvironmentState =
  | 'DESKTOP'
  | 'WINDOW_SURFACE'
  | 'WINDOW_EDGE'
  | 'CURSOR_NEAR'
  | 'CURSOR_INTERACTION'
  | 'FULLSCREEN';

export interface CharacterCoordinates {
  x: number;
  y: number;
}

export interface CharacterGaze {
  lookX: number; // -1 (left) to 1 (right)
  lookY: number; // -1 (up) to 1 (down)
}

export interface CharacterVisualConfig {
  hairColor: string;
  hairShadow: string;
  eyeColor: string;
  eyeHighlight: string;
  blazerColor: string;
  blazerTrim: string;
  skirtColor: string;
  shirtColor: string;
  tieColor: string;
  skinColor: string;
  blushColor: string;
}

export const DEFAULT_CHARACTER_PALETTE: CharacterVisualConfig = {
  hairColor: '#E26D27',      // Vibrant auburn / orange
  hairShadow: '#B84F14',     // Rich shadow
  eyeColor: '#E5A93C',       // Golden / amber
  eyeHighlight: '#FFFFFF',   // Bright shine
  blazerColor: '#6B1724',    // Burgundy / maroon school uniform
  blazerTrim: '#EAB308',     // Gold trim
  skirtColor: '#1E293B',     // Dark pleated skirt
  shirtColor: '#FFFFFF',     // Crisp white shirt
  tieColor: '#FACC15',       // Yellow tie
  skinColor: '#FFEDD5',      // Pale warm skin
  blushColor: '#FCA5A5',     // Rosy cheeks
};
