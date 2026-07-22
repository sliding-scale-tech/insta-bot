import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";
import { internal } from "./_generated/api";
import { Webhook } from "svix";

const http = httpRouter();

http.route({
  path: "/clerk-users-webhook",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    const event = await validateRequest(request);
    if (!event) {
      return new Response("Invalid webhook signature", { status: 400 });
    }

    switch (event.type) {
      case "user.created":
      case "user.updated":
        await ctx.runMutation(internal.users.upsertFromClerk, { data: event.data });
        break;
      case "user.deleted":
        if (event.data.id) {
          await ctx.runMutation(internal.users.deleteFromClerk, {
            clerkUserId: event.data.id,
          });
        }
        break;
      default:
        console.log("Ignored Clerk webhook event:", event.type);
    }

    return new Response(null, { status: 200 });
  }),
});

async function validateRequest(req: Request): Promise<any | null> {
  const payload = await req.text();
  const headers = {
    "svix-id": req.headers.get("svix-id") ?? "",
    "svix-timestamp": req.headers.get("svix-timestamp") ?? "",
    "svix-signature": req.headers.get("svix-signature") ?? "",
  };
  const secret = process.env.CLERK_WEBHOOK_SECRET;
  if (!secret) {
    console.error("CLERK_WEBHOOK_SECRET not set in Convex environment");
    return null;
  }
  try {
    const wh = new Webhook(secret);
    return wh.verify(payload, headers);
  } catch (err) {
    console.error("Clerk webhook verification failed:", err);
    return null;
  }
}

export default http;
