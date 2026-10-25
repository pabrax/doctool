import { ImageOff } from "lucide-react";
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

/** One automatic retry after this delay: a server that restarted (e.g. after a PDFium crash) gets a second chance. */
const RETRY_MS = 4000;

type Props = ImgHTMLAttributes<HTMLImageElement> & {
  src: string;
  /** Extra classes for the placeholder shown when the image fails, for callers whose img gets its size from the image itself. */
  fallbackClassName?: string;
};

/**
 * Keyed by src (and retry count): a new src is a new instance, so it starts inactive and can never paint
 * the new URL before its turn. A failed thumbnail is retried once automatically, then stays a placeholder.
 */
export function Thumb(props: Props) {
  const [retry, setRetry] = useState({ src: props.src, n: 0 });
  const n = retry.src === props.src ? retry.n : 0;
  return (
    <QueuedThumb
      key={`${props.src}|${n}`}
      {...props}
      onGiveUp={n < 1 ? () => setRetry({ src: props.src, n: n + 1 }) : undefined}
    />
  );
}

function QueuedThumb({ src, alt = "", fallbackClassName, onGiveUp, ...rest }: Props & { onGiveUp?: () => void }) {
  const [active, setActive] = useState(false);
  const [failed, setFailed] = useState(false);
  const releaseRef = useRef<() => void>(() => undefined);
  const giveUpRef = useRef(onGiveUp);
  giveUpRef.current = onGiveUp;
  const canRetry = !!onGiveUp;

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
  }, []);

  // After a failure, ask the parent for one fresh instance (new key) later; unmounting cancels it.
  useEffect(() => {
    if (!failed || !canRetry) return;
    const id = window.setTimeout(() => giveUpRef.current?.(), RETRY_MS);
    return () => window.clearTimeout(id);
  }, [failed, canRetry]);

  // A failed thumbnail shows a quiet placeholder (with an "image unavailable" glyph) instead of the browser's
  // broken-image icon. It keeps the caller's className, style (e.g. rotation) and accessible name.
  if (failed) {
    return (
      <span
        role={alt ? "img" : undefined}
        aria-label={alt || undefined}
        aria-hidden={alt ? undefined : true}
        data-thumb="failed"
        style={rest.style}
        className={`${rest.className ?? ""} ${fallbackClassName ?? ""} flex items-center justify-center text-muted`}
      >
        <ImageOff aria-hidden className="h-5 w-5 max-h-full max-w-full" />
      </span>
    );
  }
  return (
    <img
      {...rest}
      alt={alt}
      src={active ? src : undefined}
      onLoad={() => releaseRef.current()}
      onError={() => {
        releaseRef.current();
        setFailed(true);
      }}
    />
  );
}
