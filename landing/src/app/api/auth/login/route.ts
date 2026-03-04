import { NextRequest, NextResponse } from "next/server";
import { createToken, COOKIE_NAME } from "@/lib/auth";

export async function GET(request: NextRequest) {
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
