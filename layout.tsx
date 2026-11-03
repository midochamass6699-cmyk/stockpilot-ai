
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StockPilot AI",
  description: "AI-powered daily stock market scanner for US and Canadian stocks."
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
