import { useEffect, useRef } from "react";
import * as THREE from "three";
import { AudioAnalyzer, type AudioSourceMode } from "../audio/audioAnalyzer";
import orbVertexSource from "../shaders/orbVertex.glsl?raw";
import orbFragmentTemplate from "../shaders/orbFragment.glsl?raw";
import noiseSource from "../shaders/noise.glsl?raw";

const orbFragmentSource = orbFragmentTemplate.replace("__NOISE_GLSL__", noiseSource);

type OrbTheme = "nebula" | "aurora" | "plasma";
type OrbSize = "hero" | "workspace" | "panel" | "studio";
type OrbPerformanceMode = "adaptive" | "lite" | "full";

export interface AudioReactiveOrbProps {
  audioSource?: AudioSourceMode;
  audioElement?: HTMLAudioElement | null;
  active?: boolean;
  intensity?: number;
  theme?: OrbTheme;
  size?: OrbSize;
  performanceMode?: OrbPerformanceMode;
  pauseWhenOffscreen?: boolean;
  className?: string;
}

const paletteMap: Record<OrbTheme, [string, string, string]> = {
  nebula: ["#44d8ff", "#6c7cff", "#f2fbff"],
  aurora: ["#33d8a2", "#57b8ff", "#dc9cff"],
  plasma: ["#ff7c72", "#ffa84f", "#fff0ad"],
};

const sizeClassMap: Record<OrbSize, string> = {
  hero: "h-[min(76vw,46rem)] w-[min(76vw,46rem)]",
  studio: "h-[min(68vw,38rem)] w-[min(68vw,38rem)]",
  workspace: "h-[22rem] w-[22rem] md:h-[25rem] md:w-[25rem]",
  panel: "h-[18rem] w-[18rem]",
};

interface OrbUniforms {
  uTime: THREE.IUniform<number>;
  uResolution: THREE.IUniform<THREE.Vector2>;
  uAudioLow: THREE.IUniform<number>;
  uAudioMid: THREE.IUniform<number>;
  uAudioHigh: THREE.IUniform<number>;
  uOverallAmplitude: THREE.IUniform<number>;
  uMousePosition: THREE.IUniform<THREE.Vector2>;
  uColorPalette: THREE.IUniform<THREE.Vector3[]>;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

function toPaletteVectors(theme: OrbTheme): THREE.Vector3[] {
  return paletteMap[theme].map((hex) => {
    const color = new THREE.Color(hex);
    return new THREE.Vector3(color.r, color.g, color.b);
  });
}

function joinClassNames(...values: Array<string | undefined | false>): string {
  return values.filter(Boolean).join(" ");
}

export default function AudioReactiveOrb({
  audioSource = "microphone",
  audioElement = null,
  active = true,
  intensity = 1,
  theme = "nebula",
  size = "hero",
  performanceMode = "adaptive",
  pauseWhenOffscreen = true,
  className,
}: AudioReactiveOrbProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.OrthographicCamera | null>(null);
  const uniformsRef = useRef<OrbUniforms | null>(null);
  const analyzerRef = useRef<AudioAnalyzer | null>(null);
  const pointerCurrentRef = useRef(new THREE.Vector2(0.5, 0.5));
  const pointerTargetRef = useRef(new THREE.Vector2(0.5, 0.5));
  const isVisibleRef = useRef(true);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return undefined;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const autoLowPower = reduceMotion || (navigator.hardwareConcurrency ?? 8) <= 4;
    const lowPowerDevice = performanceMode === "lite" || (performanceMode === "adaptive" && autoLowPower);
    const pixelRatioCap = performanceMode === "full" ? 2 : lowPowerDevice ? 0.85 : 1.75;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, pixelRatioCap);
    const targetFrameMs = performanceMode === "full" ? 1000 / 60 : lowPowerDevice ? 1000 / 30 : 1000 / 60;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: !lowPowerDevice,
        powerPreference: lowPowerDevice ? "default" : "high-performance",
      });
    } catch (error) {
      console.warn("AudioReactiveOrb falling back to CSS-only mode:", error);
      return undefined;
    }

    rendererRef.current = renderer;
    renderer.setPixelRatio(pixelRatio);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.className = "h-full w-full";
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    cameraRef.current = camera;

    const uniforms: OrbUniforms = {
      uTime: { value: 0 },
      uResolution: { value: new THREE.Vector2(1, 1) },
      uAudioLow: { value: 0 },
      uAudioMid: { value: 0 },
      uAudioHigh: { value: 0 },
      uOverallAmplitude: { value: 0 },
      uMousePosition: { value: new THREE.Vector2(0.5, 0.5) },
      uColorPalette: { value: toPaletteVectors(theme) },
    };
    uniformsRef.current = uniforms;

    const material = new THREE.ShaderMaterial({
      vertexShader: orbVertexSource,
      fragmentShader: orbFragmentSource,
      uniforms,
      transparent: true,
      depthWrite: false,
      depthTest: false,
    });

    const geometry = new THREE.PlaneGeometry(2, 2);
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const analyzer = new AudioAnalyzer();
    analyzerRef.current = analyzer;

    const resizeRenderer = () => {
      const bounds = host.getBoundingClientRect();
      const width = Math.max(1, Math.floor(bounds.width));
      const height = Math.max(1, Math.floor(bounds.height));
      renderer.setSize(width, height, false);
      uniforms.uResolution.value.set(width, height);
    };

    const resizeObserver = new ResizeObserver(resizeRenderer);
    resizeObserver.observe(host);
    resizeRenderer();

    let intersectionObserver: IntersectionObserver | null = null;
    if (pauseWhenOffscreen && "IntersectionObserver" in window) {
      intersectionObserver = new IntersectionObserver(
        ([entry]) => {
          isVisibleRef.current = Boolean(entry?.isIntersecting);
        },
        {
          threshold: 0.02,
        },
      );
      intersectionObserver.observe(host);
    }

    const timer = new THREE.Timer();
    timer.connect(document);
    timer.reset();
    let frameId = 0;
    let lastRenderAt = 0;

    const renderFrame = (timestamp: number) => {
      frameId = window.requestAnimationFrame(renderFrame);
      if ((pauseWhenOffscreen && !isVisibleRef.current) || document.hidden) {
        return;
      }
      const now = performance.now();
      if (now - lastRenderAt < targetFrameMs) {
        return;
      }
      lastRenderAt = now;
      timer.update(timestamp);
      const elapsed = timer.getElapsed();
      const uniformsCurrent = uniformsRef.current;
      if (!uniformsCurrent) {
        return;
      }

      const bands = analyzer.sample(elapsed);
      const driftX = 0.5 + Math.sin(elapsed * 0.22) * 0.16;
      const driftY = 0.5 + Math.cos(elapsed * 0.18) * 0.12;
      const energyPull = (bands.low - bands.high) * 0.04;
      pointerTargetRef.current.set(clamp01(driftX + energyPull), clamp01(driftY - energyPull * 0.6));
      pointerCurrentRef.current.lerp(
        pointerTargetRef.current,
        0.08,
      );

      uniformsCurrent.uTime.value = elapsed;
      uniformsCurrent.uAudioLow.value = Math.min(1.25, bands.low * intensity + bands.beat * 0.16);
      uniformsCurrent.uAudioMid.value = Math.min(1.2, bands.mid * intensity);
      uniformsCurrent.uAudioHigh.value = Math.min(1.35, bands.high * intensity + bands.beat * 0.08);
      uniformsCurrent.uOverallAmplitude.value = Math.min(1.2, bands.amplitude * intensity + bands.beat * 0.1);
      uniformsCurrent.uMousePosition.value.copy(pointerCurrentRef.current);

      renderer.render(scene, camera);
    };

    frameId = window.requestAnimationFrame(renderFrame);

    return () => {
      window.cancelAnimationFrame(frameId);
      intersectionObserver?.disconnect();
      resizeObserver.disconnect();
      timer.dispose();
      analyzer.dispose();
      scene.remove(mesh);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      uniformsRef.current = null;
      rendererRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      analyzerRef.current = null;
    };
  }, [pauseWhenOffscreen, performanceMode]);

  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) {
      return;
    }
    const palette = toPaletteVectors(theme);
    uniforms.uColorPalette.value.forEach((target, index) => {
      target.copy(palette[index]);
    });
  }, [theme]);

  useEffect(() => {
    const analyzer = analyzerRef.current;
    if (!analyzer) {
      return undefined;
    }

    let cancelled = false;

    async function syncAudioSource() {
      if (!active) {
        analyzer.disconnect();
        return;
      }

      try {
        await analyzer.connect(audioSource, { audioElement });
      } catch (error) {
        if (!cancelled) {
          console.warn("AudioReactiveOrb falling back to idle mode:", error);
          analyzer.disconnect();
        }
      }
    }

    void syncAudioSource();

    return () => {
      cancelled = true;
      analyzer.disconnect();
    };
  }, [active, audioElement, audioSource]);

  return (
    <div
      className={joinClassNames(
        "orb-shell pointer-events-none relative overflow-hidden rounded-full",
        sizeClassMap[size],
        className,
      )}
      aria-hidden="true"
    >
      <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,_rgba(255,255,255,0.12),_transparent_55%),radial-gradient(circle_at_50%_62%,rgba(56,189,248,0.16),transparent_68%)] blur-xl" />
      <div ref={hostRef} className="orb-layer absolute inset-0" />
      <div className="absolute inset-[-8%] rounded-full border border-white/10 bg-transparent blur-2xl" />
    </div>
  );
}
