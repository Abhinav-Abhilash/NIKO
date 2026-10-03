import React, { useState, useEffect } from 'react';

export const DesktopPet: React.FC = () => {
  const [isDragging, setIsDragging] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Attempt to invoke Tauri startDragging if available
  const handlePointerDown = async (e: React.PointerEvent) => {
    if (e.button !== 0) return; // left click only
    setIsDragging(true);

    try {
      // Dynamic import to support both Tauri and browser environments gracefully
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const win = getCurrentWindow();
      await win.startDragging();
    } catch {
      // Running outside Tauri or data-tauri-drag-region handles it natively
    }
  };

  const handlePointerUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    const onGlobalMouseUp = () => setIsDragging(false);
    window.addEventListener('mouseup', onGlobalMouseUp);
    return () => window.removeEventListener('mouseup', onGlobalMouseUp);
  }, []);

  return (
    <div
      id="niko-desktop-pet-root"
      data-tauri-drag-region
      style={{
        width: '100vw',
        height: '100vh',
        margin: 0,
        padding: 0,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        background: 'transparent',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        overflow: 'hidden',
        pointerEvents: 'auto',
      }}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
    >
      <div
        data-tauri-drag-region
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-end',
          cursor: isDragging ? 'grabbing' : 'grab',
          filter: isDragging
            ? 'drop-shadow(0 16px 20px rgba(0, 0, 0, 0.55)) scale(1.02)'
            : 'drop-shadow(0 8px 14px rgba(0, 0, 0, 0.35))',
          transition: isDragging ? 'filter 0.15s ease' : 'transform 0.25s ease, filter 0.25s ease',
          animation: 'petIdleBreathing 3.6s ease-in-out infinite',
        }}
        title="NIKO Desktop Pet (Drag to move, Ctrl+Space to toggle)"
      >
        {/* Static Pet Sprite Placeholder */}
        <img
          data-tauri-drag-region
          src="/pet/placeholder.png"
          alt="NIKO Pet"
          draggable={false}
          onLoad={() => setImageLoaded(true)}
          style={{
            maxHeight: '235px',
            maxWidth: '190px',
            width: 'auto',
            height: 'auto',
            objectFit: 'contain',
            pointerEvents: 'auto',
            opacity: imageLoaded ? 1 : 0,
            transition: 'opacity 0.2s ease-in',
          }}
        />

        {/* Shadow base on ground */}
        <div
          data-tauri-drag-region
          style={{
            position: 'absolute',
            bottom: '2px',
            width: '90px',
            height: '10px',
            borderRadius: '50%',
            background: 'radial-gradient(ellipse at center, rgba(30, 20, 10, 0.45) 0%, rgba(0, 0, 0, 0) 75%)',
            pointerEvents: 'none',
            zIndex: -1,
          }}
        />
      </div>

      <style>{`
        @keyframes petIdleBreathing {
          0%, 100% {
            transform: translateY(0px) scale(1);
          }
          50% {
            transform: translateY(-4px) scale(1.012);
          }
        }
      `}</style>
    </div>
  );
};

export default DesktopPet;
