import { useEffect, useState } from 'react';

export function useElapsedSeconds(active: boolean): number {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) {
      return;
    }
    const startedAt = Date.now();
    const initialFrame = window.requestAnimationFrame(() => setElapsed(0));
    const timer = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => {
      window.cancelAnimationFrame(initialFrame);
      window.clearInterval(timer);
    };
  }, [active]);

  return active ? elapsed : 0;
}
