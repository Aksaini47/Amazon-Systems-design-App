import type { Metadata } from "next";
import "./globals.css";
import NavBar from "./NavBar";

export const metadata: Metadata = {
  title: "RepairFully — Video Manager",
  description: "Amazon seller packing/unpacking video manager",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen antialiased">
        <NavBar />
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
