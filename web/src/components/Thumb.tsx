import { useEffect, useRef, useState, type ImgHTMLAttributes } from "react";

/**
 * Thumbnails are rendered by PDFium on the server, which is not safe under concurrent requests
 * (observed: access violation that kills the server when a page asks for many at once).
 * Every Thumb therefore waits for its turn and loads one image at a time.
 */
let tail: Promise<void> = Promise.resolve();
const SAFETY_MS = 6000;

function takeTurn(): { turn: Promise<void>; release: () => void } {
  let release!: () => void;
  const done = new Promise<void>((resolve) => (release = resolve));
  const turn = tail;
  tail = tail.then(() => done);
  return { turn, release };
}

export function Thumb({ src, alt = "", ...rest }: ImgHTMLAttributes<HTMLImageElement> & { src: string }) {
  const [active, setActive] = useState(false);
  const releaseRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    let cancelled = false;
    const { turn, release } = takeTurn();
    releaseRef.current = release;
    const timer = { id: 0 };
    void turn.then(() => {
      if (cancelled) return release();
      setActive(true);
      timer.id = window.setTimeout(release, SAFETY_MS);
    });
    return () => {
      cancelled = true;
      window.clearTimeout(timer.id);
      release();
    };
  }, [src]);

  return <img {...rest} alt={alt} src={active ? src : undefined} onLoad={() => releaseRef.current()} onError={() => releaseRef.current()} />;
}
