import "./globals.css";

export const metadata = {
  title: "OBR Macroeconomic Model — Emulator Dashboard",
  description:
    "Interactive dashboard for an independent Python re-implementation of the OBR's published macroeconomic model: explore policy scenarios, browse the 372 published equations, and search every model variable.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
