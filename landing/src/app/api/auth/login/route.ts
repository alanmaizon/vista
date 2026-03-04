import { NextRequest, NextResponse } from "next/server";
import { createToken, COOKIE_NAME } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  // TODO: In production, verify user credentials (e.g. Firebase ID token
  // forwarded from a client-side sign-in flow) before issuing a session token.
  const token = await createToken({ role: "user", provider: "server" });

  const url = request.nextUrl.clone();
  url.pathname = "/workspace";

  const response = NextResponse.redirect(url);

  response.cookies.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8, // 8 hours
  });

  return response;
}
