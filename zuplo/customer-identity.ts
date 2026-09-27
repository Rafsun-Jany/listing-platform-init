import { environment, ZuploContext, ZuploRequest } from "@zuplo/runtime";

// Run after API Key Authentication and before the upstream URL Rewrite handler.
export default async function customerIdentity(request: ZuploRequest, _context: ZuploContext) {
  const subject = request.user?.sub;
  const secret = environment.GATEWAY_SECRET;
  const staff = new Set((environment.STAFF_SUBJECTS || "").split(",").map((s: string) => s.trim()).filter(Boolean));
  if (!subject || !secret || staff.has(subject)) {
    return new Response("Customer API key required", { status: 403 });
  }
  // set() replaces any identity headers provided by the client.
  request.headers.set("x-gateway-secret", secret);
  request.headers.set("x-consumer-id", subject);
  request.headers.set("x-consumer-role", "customer");
  return request;
}
