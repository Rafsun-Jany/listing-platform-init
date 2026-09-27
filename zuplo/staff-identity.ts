import { environment, ZuploContext, ZuploRequest } from "@zuplo/runtime";

// Keep STAFF_SUBJECTS provider-controlled; never let portal users edit it.
export default async function staffIdentity(request: ZuploRequest, _context: ZuploContext) {
  const subject = request.user?.sub;
  const secret = environment.GATEWAY_SECRET;
  const staff = new Set((environment.STAFF_SUBJECTS || "").split(",").map((s: string) => s.trim()).filter(Boolean));
  if (!subject || !secret || !staff.has(subject)) {
    return new Response("Staff API key required", { status: 403 });
  }
  request.headers.set("x-gateway-secret", secret);
  request.headers.set("x-consumer-id", subject);
  request.headers.set("x-consumer-role", "staff");
  return request;
}
