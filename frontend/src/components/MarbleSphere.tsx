import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { useLoader, useThree } from "@react-three/fiber";
import { useMemo } from "react";

type MarbleSphereProps = {
  className?: string;
};

export default function MarbleSphere({ className = "" }: MarbleSphereProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return undefined;
    }

    let frameId = 0;
    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;

    try {
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
      camera.position.set(0, 0, 5.8);

      const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "low-power",
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      host.appendChild(renderer.domElement);

      const texture = useLoader(THREE.TextureLoader, "/marble-pattern.png");
      const { gl } = useThree();

      useMemo(() => {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.anisotropy = gl.capabilities.getMaxAnisotropy();
        texture.needsUpdate = true;
      }, [texture, gl]);

      const geometry = new THREE.SphereGeometry(1.45, 72, 72);
      const material = new THREE.MeshStandardMaterial({
        map: texture,
        roughness: 0.84,
        metalness: 0.03,
      });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.rotation.x = 0.12;
      sphere.rotation.z = -0.08;
      scene.add(sphere);

      const ambientLight = new THREE.AmbientLight(0xffffff, 1.4);
      const keyLight = new THREE.DirectionalLight(0xffffff, 1.55);
      keyLight.position.set(3.2, 2.4, 5.4);
      const rimLight = new THREE.DirectionalLight(0xdfe4eb, 0.9);
      rimLight.position.set(-4.4, -1.8, 2.6);
      scene.add(ambientLight, keyLight, rimLight);

      const timer = new THREE.Timer();

      const resize = () => {
        const width = host.clientWidth || 1;
        const height = host.clientHeight || 1;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false);
      };

      resize();
      resizeObserver = new ResizeObserver(() => resize());
      resizeObserver.observe(host);

      const render = () => {
        if (disposed) {
          return;
        }
        timer.update();
        const elapsed = timer.getElapsed();
        sphere.rotation.y += 0.002;
        sphere.rotation.x = 0.12 + Math.sin(elapsed * 0.55) * 0.015;
        sphere.rotation.z = -0.08 + Math.cos(elapsed * 0.35) * 0.02;
        renderer.render(scene, camera);
        frameId = window.requestAnimationFrame(render);
      };

      render();

      return () => {
        disposed = true;
        window.cancelAnimationFrame(frameId);
        resizeObserver?.disconnect();
        geometry.dispose();
        material.dispose();
        texture.dispose();
        renderer.dispose();
        renderer.domElement.remove();
      };
    } catch (error) {
      console.warn("MarbleSphere falling back to CSS-only mode:", error);
      setFallback(true);
      return () => {
        resizeObserver?.disconnect();
      };
    }
  }, []);

  return (
    <div
      ref={hostRef}
      className={`marble-surface ${fallback ? "marble-surface-fallback" : ""} ${className}`.trim()}
      aria-hidden="true"
    />
  );
}
