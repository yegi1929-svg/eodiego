/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  /** D(BFF)의 base URL. 없으면 /ui/* 프록시를 하지 않는다. */
  BFF_BASE_URL?: string;
  /** D가 요구하는 공유 시크릿. 이 worker를 거친 요청임을 증명한다. */
  BFF_GATEWAY_TOKEN?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // 화면이 부르는 /ui/* 는 D(BFF)로 그대로 넘긴다. 같은 origin으로 유지해야
    // 세션 쿠키가 CORS 제약 없이 오간다 (dev 서버의 server.proxy와 같은 역할).
    // `vinext start`는 워커를 Node에서 돌리며 env를 넘기지 않으므로 둘 다 본다.
    if (url.pathname.startsWith("/ui/")) {
      const bffBaseUrl =
        env?.BFF_BASE_URL || (typeof process !== "undefined" ? process.env?.BFF_BASE_URL : undefined);
      if (bffBaseUrl) {
        const target = new URL(url.pathname + url.search, bffBaseUrl);
        const proxied = new Request(target, request);
        // 공유 시크릿을 붙여 "화면을 거친 요청"임을 D에 증명한다. 브라우저가
        // 보낸 같은 이름의 헤더는 여기서 덮어쓰므로 위조할 수 없다.
        const gatewayToken =
          env?.BFF_GATEWAY_TOKEN ||
          (typeof process !== "undefined" ? process.env?.BFF_GATEWAY_TOKEN : undefined);
        if (gatewayToken) proxied.headers.set("x-bff-token", gatewayToken);
        else proxied.headers.delete("x-bff-token");
        return fetch(proxied);
      }
    }

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;
