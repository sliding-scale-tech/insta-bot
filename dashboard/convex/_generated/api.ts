/* eslint-disable */
// Stub until `npx convex dev` generates the real file.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const api: any = new Proxy({}, { get: (_t, p) => new Proxy({}, { get: (_t2, p2) => `${String(p)}:${String(p2)}` }) })
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const internal: any = api
