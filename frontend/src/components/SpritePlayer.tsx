import React, { useEffect, useRef, useState, useCallback } from 'react';

export interface PetManifestState {
  fps: number;
  loop: boolean;
  frames: string[];
  description: string;
}

export interface PetManifest {
  source: string;
  canvas: {
    width: number;
    height: number;
    anchor_y: number;
    scale: number;
  };
  states: Record<string, PetManifestState>;
}

export interface SpritePlayerProps {
  state: string;
  direction?: 'left' | 'right';
  sizeScale?: number; // 0.5 to 1.5 (default 1.0)
  isPaused?: boolean;
  onStateFinish?: (finishedState: string) => void;
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
  onContextMenu?: (e: React.MouseEvent<HTMLDivElement>) => void;
  onPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void;
  onPointerUp?: (e: React.PointerEvent<HTMLDivElement>) => void;
  className?: string;
  style?: React.CSSProperties;
  'data-testid'?: string;
}

// Global in-memory cache for preloaded HTMLImageElement and manifest
let cachedManifest: PetManifest | null = null;
const imageCache = new Map<string, HTMLImageElement>();
let isPreloadingStarted = false;

export async function preloadPetManifestAndFrames(
  manifestUrl = '/pet/manifest.json'
): Promise<PetManifest | null> {
  if (cachedManifest && imageCache.size > 0) {
    return cachedManifest;
  }

  try {
    const res = await fetch(manifestUrl);
    if (!res.ok) {
      throw new Error(`Failed to load manifest: ${res.statusText}`);
    }
    const manifest: PetManifest = await res.json();
    cachedManifest = manifest;

    // Preload & decode all frame images across all states in parallel
    const promises: Promise<void>[] = [];

    for (const [stateName, stateData] of Object.entries(manifest.states)) {
      for (const frameName of stateData.frames) {
        const frameUrl = `/pet/${stateName}/${frameName}`;
        if (!imageCache.has(frameUrl)) {
          const p = (async () => {
            try {
              const img = new Image();
              img.src = frameUrl;
              if ('decode' in img) {
                await img.decode().catch(() => {});
              }
              imageCache.set(frameUrl, img);
            } catch {
              // Gracefully handle individual frame load errors
            }
          })();
          promises.push(p);
        }
      }
    }

    await Promise.all(promises);
    return manifest;
  } catch (err) {
    console.warn('[SpritePlayer] Error preloading pet sprites:', err);
    return null;
  }
}

export const SpritePlayer: React.FC<SpritePlayerProps> = ({
  state,
  direction = 'left',
  sizeScale = 1.0,
  isPaused = false,
  onStateFinish,
  onClick,
  onContextMenu,
  onPointerDown,
  onPointerUp,
  className = '',
  style = {},
  'data-testid': testId = 'niko-sprite-player',
}) => {
  const [manifest, setManifest] = useState<PetManifest | null>(() => cachedManifest);
  const [frameIndex, setFrameIndex] = useState<number>(0);
  const [isLoaded, setIsLoaded] = useState<boolean>(Boolean(cachedManifest && imageCache.size > 0));
  const [isVisible, setIsVisible] = useState<boolean>(
    typeof document !== 'undefined' ? document.visibilityState !== 'hidden' : true
  );

  const currentFrameRef = useRef<number>(0);
  const lastTickTimeRef = useRef<number>(0);
  const animFrameIdRef = useRef<number | null>(null);
  const onFinishRef = useRef(onStateFinish);
  onFinishRef.current = onStateFinish;

  // Track window visibility to pause animation and achieve < 1% CPU
  useEffect(() => {
    const handleVisibility = () => {
      setIsVisible(document.visibilityState !== 'hidden');
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  // Preload manifest on mount if not already cached
  useEffect(() => {
    let mounted = true;
    if (!cachedManifest && !isPreloadingStarted) {
      isPreloadingStarted = true;
      preloadPetManifestAndFrames().then((m) => {
        if (mounted && m) {
          setManifest(m);
          setIsLoaded(true);
        }
      });
    } else if (cachedManifest && !manifest) {
      setManifest(cachedManifest);
      setIsLoaded(true);
    }
    return () => {
      mounted = false;
    };
  }, [manifest]);

  // Reset frame when state changes
  useEffect(() => {
    currentFrameRef.current = 0;
    setFrameIndex(0);
    lastTickTimeRef.current = performance.now();
  }, [state]);

  // Animation Loop via requestAnimationFrame
  const animate = useCallback(
    (now: number) => {
      if (!manifest || !manifest.states[state] || isPaused || !isVisible) {
        animFrameIdRef.current = requestAnimationFrame(animate);
        return;
      }

      const stateData = manifest.states[state];
      const fps = Math.max(1, stateData.fps || 4);
      const frameInterval = 1000 / fps;

      if (!lastTickTimeRef.current) {
        lastTickTimeRef.current = now;
      }

      const elapsed = now - lastTickTimeRef.current;

      if (elapsed >= frameInterval) {
        // Advance frame
        lastTickTimeRef.current = now - (elapsed % frameInterval);
        const totalFrames = stateData.frames.length;

        if (totalFrames > 0) {
          const nextIndex = currentFrameRef.current + 1;
          if (nextIndex >= totalFrames) {
            if (stateData.loop) {
              currentFrameRef.current = 0;
              setFrameIndex(0);
            } else {
              // Non-looping state: freeze on final frame and signal completion
              currentFrameRef.current = totalFrames - 1;
              setFrameIndex(totalFrames - 1);
              if (onFinishRef.current) {
                onFinishRef.current(state);
              }
            }
          } else {
            currentFrameRef.current = nextIndex;
            setFrameIndex(nextIndex);
          }
        }
      }

      animFrameIdRef.current = requestAnimationFrame(animate);
    },
    [manifest, state, isPaused, isVisible]
  );

  useEffect(() => {
    if (isPaused || !isVisible) {
      if (animFrameIdRef.current !== null) {
        cancelAnimationFrame(animFrameIdRef.current);
        animFrameIdRef.current = null;
      }
      return;
    }

    lastTickTimeRef.current = performance.now();
    animFrameIdRef.current = requestAnimationFrame(animate);

    return () => {
      if (animFrameIdRef.current !== null) {
        cancelAnimationFrame(animFrameIdRef.current);
        animFrameIdRef.current = null;
      }
    };
  }, [animate, isPaused, isVisible]);

  // Determine current frame image path
  const stateData = manifest?.states[state];
  const frames = stateData?.frames || ['frame_0.png'];
  const safeFrameIndex = Math.min(frameIndex, frames.length - 1);
  const frameFilename = frames[safeFrameIndex] || 'frame_0.png';
  const frameSrc = `/pet/${state}/${frameFilename}`;

  // Mirroring for directional states (walking, running)
  const shouldMirror =
    direction === 'right' && (state === 'walking' || state === 'running');

  // Clamp sizeScale between 0.5x and 1.5x
  const clampedScale = Math.max(0.5, Math.min(1.5, sizeScale));

  // Canvas size: base 200x240 (exported at 2x HiDPI for crispness)
  const baseW = manifest?.canvas.width || 200;
  const baseH = manifest?.canvas.height || 240;

  return (
    <div
      data-testid={testId}
      className={`niko-sprite-player-root ${className}`}
      onClick={onClick}
      onContextMenu={onContextMenu}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      style={{
        position: 'relative',
        width: `${baseW}px`,
        height: `${baseH}px`,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        transform: `scale(${clampedScale})`,
        transformOrigin: 'bottom center',
        transition: 'transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        pointerEvents: 'auto',
        ...style,
      }}
    >
      {/* Sprite Image Container with Smooth Breathing Bob */}
      <div
        className="niko-sprite-container"
        data-testid="niko-sprite-container"
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'center',
          transform: shouldMirror ? 'scaleX(-1)' : 'none',
          animation:
            state === 'sleeping'
              ? 'petSleepBreathing 4.5s ease-in-out infinite'
              : state === 'walking' || state === 'running'
                ? 'none'
                : 'petGentleBob 3.2s ease-in-out infinite',
        }}
      >
        <img
          data-testid="niko-sprite-image"
          src={frameSrc}
          alt={`Pet state ${state} frame ${safeFrameIndex}`}
          draggable={false}
          style={{
            width: `${baseW}px`,
            height: `${baseH}px`,
            objectFit: 'contain',
            imageRendering: 'auto',
            opacity: isLoaded ? 1 : 0.85,
            transition: 'opacity 0.15s ease-out',
            pointerEvents: 'auto',
          }}
        />

        {/* Soft Radial Contact Shadow */}
        <div
          data-testid="niko-sprite-shadow"
          style={{
            position: 'absolute',
            bottom: '4px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: state === 'sleeping' ? '120px' : '90px',
            height: '10px',
            borderRadius: '50%',
            background:
              'radial-gradient(ellipse at center, rgba(30, 20, 15, 0.42) 0%, rgba(0, 0, 0, 0) 75%)',
            pointerEvents: 'none',
            zIndex: -1,
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      <style>{`
        @keyframes petGentleBob {
          0%, 100% {
            transform: translateY(0px) scale(1, 1);
          }
          50% {
            transform: translateY(-3px) scale(1.008, 1.012);
          }
        }

        @keyframes petSleepBreathing {
          0%, 100% {
            transform: translateY(0px) scale(1, 1);
          }
          50% {
            transform: translateY(-2px) scale(1.015, 1.02);
          }
        }
      `}</style>
    </div>
  );
};

export default SpritePlayer;
