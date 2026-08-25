import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "어디GO | 제주 여행 추천",
  description: "AI로 가볍게, 제주를 깊게. 여행 일정과 실시간 제주 추천을 한곳에서 만나보세요.",
  openGraph: { title: "어디GO! | 제주 여행 추천", description: "AI로 가볍게, 제주를 깊게.", images: ["/og.png"] },
  twitter: { card: "summary_large_image", title: "어디GO! | 제주 여행 추천", description: "AI로 가볍게, 제주를 깊게.", images: ["/og.png"] },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
