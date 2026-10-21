import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Meridian • Solana Intelligence", description: "Local, explainable paper trading research terminal" };
export default function Layout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }
