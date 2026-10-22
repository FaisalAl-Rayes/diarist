"use client";

import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export function AccountControls() {
  return (
    <div className="flex items-center gap-2">
      <Show when="signed-out">
        <SignInButton mode="redirect">
          <Button variant="ghost" size="sm">Sign in</Button>
        </SignInButton>
        <SignUpButton mode="redirect">
          <Button variant="outline" size="sm">Sign up</Button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <UserButton />
      </Show>
    </div>
  );
}
