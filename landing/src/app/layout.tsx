import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Eurydice – Intelligent Digital Music Tutor",
  description:
    "An intelligent digital music tutor that provides deep performance feedback, adaptive learning paths, and real-time collaboration.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
