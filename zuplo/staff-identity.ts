import { ZuploContext, ZuploRequest } from "@zuplo/runtime";

// Keep STAFF_SUBJECTS provider-controlled; never let portal users edit it.
export default async function staffIdentity(request: ZuploRequest, context: ZuploContext) {
  const subject = request.user?.sub;
  const secret = context.env.GATEWAY_SECRET;
  const staff = new Set((context.env.STAFF_SUBJECTS || "").split(",").map((s: string) => s.trim()).filter(Boolean));
  if (!subject || !secret || !staff.has(subject)) {
    return new Response("Staff API key required", { status: 403 });
  }
  request.headers.set("x-gateway-secret", secret);
  request.headers.set("x-consumer-id", subject);
  request.headers.set("x-consumer-role", "staff");
  return request;
}

