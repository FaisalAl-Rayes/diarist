import { expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactNode } from "react";
const { session } = vi.hoisted(() => ({ session: { signedIn: false } }));
vi.mock("@clerk/nextjs", () => ({
  Show: ({ when, children }: { when: string; children: ReactNode }) => (when === "signed-in") === session.signedIn ? children : null,
  SignInButton: ({ children }: { children: ReactNode }) => children,
  SignUpButton: ({ children }: { children: ReactNode }) => children,
  UserButton: () => <button>Manage account and sign out</button>,
}));
import { AccountControls } from "./account-controls";

it("offers sign in and signup when signed out", () => {
  session.signedIn = false;
  const html = renderToStaticMarkup(<AccountControls />);
  expect(html).toContain("Sign in");
  expect(html).toContain("Sign up");
  expect(html).not.toContain("Manage account");
});
it("offers the user menu with signout when signed in", () => {
  session.signedIn = true;
  const html = renderToStaticMarkup(<AccountControls />);
  expect(html).toContain("Manage account and sign out");
  expect(html).not.toContain("Sign in");
});
