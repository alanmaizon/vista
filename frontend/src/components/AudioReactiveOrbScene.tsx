import { useEffect, useRef } from "react";
import * as THREE from "three";
import { AudioAnalyzer, type AudioSourceMode } from "../audio/audioAnalyzer";
import orbVertexSource from "../shaders/orbVertex.glsl?raw";
import orbFragmentTemplate from "../shaders/orbFragment.glsl?raw";
import noiseSource from "../shaders/noise.glsl?raw";

const orbFragmentSource = orbFragmentTemplate.replace("__NOISE_GLSL__", noiseSource);

type OrbTheme = "nebula" | "aurora" | "plasma";
type OrbSize = "hero" | "workspace" | "panel";

export interface AudioReactiveOrbProps {
  audioSource?: AudioSourceMode;
  audioElement?: HTMLAudioElement | null;
  active?: boolean;
  intensity?: number;
  theme?: OrbTheme;
  size?: OrbSize;
  className?: string;
}

const paletteMap: Record<OrbTheme, [string, string, string]> = {
  nebula: ["#44d8ff", "#6c7cff", "#f2fbff"],
  aurora: ["#33d8a2", "#57b8ff", "#dc9cff"],
  plasma: ["#ff7c72", "#ffa84f", "#fff0ad"],
};

const sizeClassMap: Record<OrbSize, string> = {
  hero: "h-[min(76vw,46rem)] w-[min(76vw,46rem)]",
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
  className,
}: AudioReactiveOrbProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.OrthographicCamera | null>(null);
  const uniformsRef = useRef<OrbUniforms | null>(null);
  const analyzerRef = useRef<AudioAnalyzer | null>(null);
  const pointerTargetRef = useRef(new THREE.Vector2(0.5, 0.5));
  const pointerCurrentRef = useRef(new THREE.Vector2(0.5, 0.5));

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return undefined;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const lowPowerDevice = reduceMotion || (navigator.hardwareConcurrency ?? 8) <= 4;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, lowPowerDevice ? 1 : 1.75);

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

    // Map pointer motion into the orb's local bounds so parallax still feels natural
    // when the orb is used in different layouts.
    const onPointerMove = (event: PointerEvent) => {
      const bounds = host.getBoundingClientRect();
      const normalizedX = bounds.width ? (event.clientX - bounds.left) / bounds.width : 0.5;
      const normalizedY = bounds.height ? (event.clientY - bounds.top) / bounds.height : 0.5;
      pointerTargetRef.current.set(clamp01(normalizedX), 1 - clamp01(normalizedY));
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });

    const clock = new THREE.Clock();
    let frameId = 0;

    const renderFrame = () => {
      frameId = window.requestAnimationFrame(renderFrame);
      const elapsed = clock.getElapsedTime();
      const uniformsCurrent = uniformsRef.current;
      if (!uniformsCurrent) {
        return;
      }

      const bands = analyzer.sample(elapsed);
      pointerCurrentRef.current.lerp(pointerTargetRef.current, 0.06);

      uniformsCurrent.uTime.value = elapsed;
      uniformsCurrent.uAudioLow.value = Math.min(1.25, bands.low * intensity + bands.beat * 0.16);
      uniformsCurrent.uAudioMid.value = Math.min(1.2, bands.mid * intensity);
      uniformsCurrent.uAudioHigh.value = Math.min(1.35, bands.high * intensity + bands.beat * 0.08);
      uniformsCurrent.uOverallAmplitude.value = Math.min(1.2, bands.amplitude * intensity + bands.beat * 0.1);
      uniformsCurrent.uMousePosition.value.copy(pointerCurrentRef.current);

      renderer.render(scene, camera);
    };

    renderFrame();

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("pointermove", onPointerMove);
      resizeObserver.disconnect();
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
  }, []);

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
