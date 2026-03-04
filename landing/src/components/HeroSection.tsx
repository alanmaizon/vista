"use client";

import { motion } from "framer-motion";

export default function HeroSection() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-gray-950 text-white">
      {/* Animated gradient background */}
      <div className="pointer-events-none absolute inset-0">
        <motion.div
          className="absolute inset-0 opacity-40"
          style={{
            background:
              "radial-gradient(ellipse at 30% 50%, #6366f1 0%, transparent 60%), radial-gradient(ellipse at 70% 50%, #8b5cf6 0%, transparent 60%)",
          }}
          animate={{
            background: [
              "radial-gradient(ellipse at 30% 50%, #6366f1 0%, transparent 60%), radial-gradient(ellipse at 70% 50%, #8b5cf6 0%, transparent 60%)",
              "radial-gradient(ellipse at 50% 30%, #818cf8 0%, transparent 60%), radial-gradient(ellipse at 50% 70%, #a78bfa 0%, transparent 60%)",
              "radial-gradient(ellipse at 70% 50%, #6366f1 0%, transparent 60%), radial-gradient(ellipse at 30% 50%, #8b5cf6 0%, transparent 60%)",
              "radial-gradient(ellipse at 30% 50%, #6366f1 0%, transparent 60%), radial-gradient(ellipse at 70% 50%, #8b5cf6 0%, transparent 60%)",
            ],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
        />
      </div>

      {/* Content */}
      <motion.div
        className="relative z-10 flex flex-col items-center gap-6 px-6 text-center"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      >
        {/* Logo placeholder */}
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-white/10 backdrop-blur-sm text-5xl">
          🎵
        </div>

        <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight">
          Eurydice
        </h1>

        <p className="text-lg sm:text-xl md:text-2xl text-gray-300 max-w-xl">
          An Intelligent Digital Music Tutor
        </p>

        <a
          href="/api/auth/login"
          className="mt-4 inline-flex items-center gap-2 rounded-full bg-white px-8 py-3 text-base font-semibold text-gray-900 shadow-lg transition-transform hover:scale-105 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-white/50"
        >
          Login
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 12h14" />
            <path d="m12 5 7 7-7 7" />
          </svg>
        </a>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-10 z-10 flex flex-col items-center gap-2 text-gray-400"
        animate={{ y: [0, 8, 0] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      >
        <span className="text-xs uppercase tracking-widest">Scroll</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </motion.div>
    </section>
  );
}
