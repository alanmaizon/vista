"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

export interface FeatureSection {
  title: string;
  description: string;
  icon: string;
}

interface ParallaxSectionProps {
  section: FeatureSection;
  index: number;
}

export default function ParallaxSection({
  section,
  index,
}: ParallaxSectionProps) {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });

  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], ["8%", "-8%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.8, 1], [0, 1, 1, 0]);

  const isDark = index % 2 === 1;

  return (
    <section
      ref={ref}
      className={`relative min-h-[90vh] flex items-center justify-center overflow-hidden ${
        isDark ? "bg-gray-950 text-white" : "bg-white text-gray-900"
      }`}
    >
      {/* Parallax background accent */}
      <motion.div
        style={{ y: bgY }}
        className={`absolute inset-0 ${
          isDark
            ? "bg-gradient-to-br from-gray-900 via-gray-950 to-black"
            : "bg-gradient-to-br from-gray-50 via-white to-gray-100"
        }`}
      />

      {/* Content */}
      <motion.div
        style={{ y: contentY, opacity }}
        className="relative z-10 max-w-3xl mx-auto px-6 text-center"
      >
        {/* Icon placeholder */}
        <div
          className={`mx-auto mb-8 flex h-20 w-20 items-center justify-center rounded-2xl text-4xl ${
            isDark ? "bg-white/10" : "bg-gray-100"
          }`}
        >
          {section.icon}
        </div>

        <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight mb-6">
          {section.title}
        </h2>

        <p
          className={`text-lg sm:text-xl leading-relaxed max-w-2xl mx-auto ${
            isDark ? "text-gray-300" : "text-gray-600"
          }`}
        >
          {section.description}
        </p>
      </motion.div>
    </section>
  );
}
