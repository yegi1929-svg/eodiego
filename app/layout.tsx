import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://eodiego.yegi1929.chatgpt.site"),
  title: "어디GO | 제주 여행 추천",
  description: "오늘 제주, 어디GO? 취향에 맞는 제주 여행 동선과 추천 장소를 한곳에서 만나보세요.",
  openGraph: { title: "어디GO! | 제주 여행 추천", description: "오늘 제주, 어디GO? 취향에 맞는 여행 동선과 추천 장소를 만나보세요.", images: ["/og.png"] },
  twitter: { card: "summary_large_image", title: "어디GO! | 제주 여행 추천", description: "오늘 제주, 어디GO? 취향에 맞는 여행 동선과 추천 장소를 만나보세요.", images: ["/og.png"] },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
