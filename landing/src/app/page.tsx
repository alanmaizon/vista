import HeroSection from "@/components/HeroSection";
import ParallaxSection from "@/components/ParallaxSection";
import { featureSections } from "@/lib/sections";

export default function LandingPage() {
  return (
    <main>
      <HeroSection />
      {featureSections.map((section, index) => (
        <ParallaxSection key={section.title} section={section} index={index} />
      ))}
    </main>
  );
}

