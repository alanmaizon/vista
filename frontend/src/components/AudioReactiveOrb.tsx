import { Suspense, lazy, useEffect, useState } from "react";
import type { AudioReactiveOrbProps } from "./AudioReactiveOrbScene";

const AudioReactiveOrbScene = lazy(() => import("./AudioReactiveOrbScene"));

type AudioReactiveOrbWrapperProps = AudioReactiveOrbProps & {
  deferMount?: boolean;
};

const sizeClassMap = {
  hero: "h-[min(76vw,46rem)] w-[min(76vw,46rem)]",
  workspace: "h-[22rem] w-[22rem] md:h-[25rem] md:w-[25rem]",
  panel: "h-[18rem] w-[18rem]",
} as const;

function joinClassNames(...values: Array<string | undefined | false>): string {
  return values.filter(Boolean).join(" ");
}

function AudioReactiveOrbFallback({
  size = "hero",
  className,
}: Pick<AudioReactiveOrbProps, "size" | "className">) {
  return (
    <div
      className={joinClassNames(
        "orb-shell pointer-events-none relative overflow-hidden rounded-full",
        sizeClassMap[size],
        className,
      )}
      aria-hidden="true"
    >
      <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_50%_45%,rgba(125,211,252,0.22),transparent_34%),radial-gradient(circle_at_55%_60%,rgba(99,102,241,0.2),transparent_56%),radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_68%)] blur-xl" />
      <div className="absolute inset-[16%] rounded-full border border-white/12 bg-[radial-gradient(circle_at_50%_45%,rgba(255,255,255,0.08),rgba(56,189,248,0.06)_38%,rgba(8,15,34,0.0)_72%)]" />
      <div className="absolute inset-[-8%] rounded-full border border-white/10 bg-transparent blur-2xl" />
    </div>
  );
}

export type { AudioReactiveOrbProps } from "./AudioReactiveOrbScene";

export default function AudioReactiveOrb({
  deferMount = false,
  ...props
}: AudioReactiveOrbWrapperProps) {
  const [shouldMount, setShouldMount] = useState(!deferMount);

  useEffect(() => {
    if (!deferMount) {
      setShouldMount(true);
      return undefined;
    }

    let cancelled = false;
    let timeoutId: number | null = null;
    const idleWindow = window as Window & typeof globalThis & {
      requestIdleCallback?: (
        callback: IdleRequestCallback,
        options?: IdleRequestOptions,
      ) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    const idleCallback =
      typeof idleWindow.requestIdleCallback === "function"
        ? idleWindow.requestIdleCallback(() => {
            if (!cancelled) {
              setShouldMount(true);
            }
          }, { timeout: 1200 })
        : null;

    if (idleCallback == null) {
      timeoutId = window.setTimeout(() => {
        if (!cancelled) {
          setShouldMount(true);
        }
      }, 320);
    }

    return () => {
      cancelled = true;
      if (idleCallback != null && typeof idleWindow.cancelIdleCallback === "function") {
        idleWindow.cancelIdleCallback(idleCallback);
      }
      if (timeoutId != null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [deferMount]);

  if (!shouldMount) {
    return <AudioReactiveOrbFallback size={props.size} className={props.className} />;
  }

  return (
    <Suspense fallback={<AudioReactiveOrbFallback size={props.size} className={props.className} />}>
      <AudioReactiveOrbScene {...props} />
    </Suspense>
  );
}
