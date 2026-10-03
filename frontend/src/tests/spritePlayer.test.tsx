import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { SpritePlayer, preloadPetManifestAndFrames } from '../components/SpritePlayer';

const MOCK_MANIFEST = {
  source: 'character-sheet.png',
  canvas: {
    width: 200,
    height: 240,
    anchor_y: 216,
    scale: 2.0,
  },
  states: {
    idle: {
      fps: 4,
      loop: true,
      frames: ['frame_0.png', 'frame_1.png', 'frame_2.png', 'frame_3.png'],
      description: 'Idle standing',
    },
    walking: {
      fps: 6,
      loop: true,
      frames: ['frame_0.png', 'frame_1.png', 'frame_2.png'],
      description: 'Walking stride',
    },
    running: {
      fps: 8,
      loop: true,
      frames: ['frame_0.png', 'frame_1.png'],
      description: 'Running sprint',
    },
    success: {
      fps: 4,
      loop: false,
      frames: ['frame_0.png', 'frame_1.png'],
      description: 'Success celebration',
    },
  },
};

describe('SpritePlayer Component', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => MOCK_MANIFEST,
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders correctly and loads manifest frames', async () => {
    await act(async () => {
      render(<SpritePlayer state="idle" />);
    });

    const playerRoot = screen.getByTestId('niko-sprite-player');
    expect(playerRoot).toBeDefined();

    const img = screen.getByTestId('niko-sprite-image');
    expect(img).toBeDefined();
    expect(img.getAttribute('src')).toBe('/pet/idle/frame_0.png');
  });

  it('applies scaleX(-1) mirroring when direction is right for walking and running', async () => {
    const { rerender } = render(<SpritePlayer state="walking" direction="right" />);
    let container = screen.getByTestId('niko-sprite-container');
    expect(container.style.transform).toBe('scaleX(-1)');

    // Test running state also mirrors
    rerender(<SpritePlayer state="running" direction="right" />);
    container = screen.getByTestId('niko-sprite-container');
    expect(container.style.transform).toBe('scaleX(-1)');

    // Left direction should not mirror
    rerender(<SpritePlayer state="walking" direction="left" />);
    container = screen.getByTestId('niko-sprite-container');
    expect(container.style.transform).toBe('none');

    // Non-directional states (idle) should not mirror even if direction is right
    rerender(<SpritePlayer state="idle" direction="right" />);
    container = screen.getByTestId('niko-sprite-container');
    expect(container.style.transform).toBe('none');
  });

  it('clamps size scale between 0.5x and 1.5x', async () => {
    const { rerender } = render(<SpritePlayer state="idle" sizeScale={1.2} />);
    let playerRoot = screen.getByTestId('niko-sprite-player');
    expect(playerRoot.style.transform).toBe('scale(1.2)');

    // Scale below 0.5 is clamped to 0.5
    rerender(<SpritePlayer state="idle" sizeScale={0.2} />);
    playerRoot = screen.getByTestId('niko-sprite-player');
    expect(playerRoot.style.transform).toBe('scale(0.5)');

    // Scale above 1.5 is clamped to 1.5
    rerender(<SpritePlayer state="idle" sizeScale={2.5} />);
    playerRoot = screen.getByTestId('niko-sprite-player');
    expect(playerRoot.style.transform).toBe('scale(1.5)');
  });

  it('supports preloadPetManifestAndFrames utility', async () => {
    const result = await preloadPetManifestAndFrames('/pet/manifest.json');
    expect(result).toBeDefined();
    expect(result?.states.idle).toBeDefined();
  });
});
