export default {
  providers: [
    {
      // Set JWT_ISSUER_DOMAIN in the Convex dashboard (Settings → Environment
      // Variables) to your Clerk Frontend API URL, e.g.
      //   https://ruling-civet-84.clerk.accounts.dev
      domain: process.env.JWT_ISSUER_DOMAIN,
      applicationID: "convex",
    },
  ],
};
