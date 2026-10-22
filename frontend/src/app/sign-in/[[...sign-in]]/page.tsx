import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full flex-col items-center justify-center gap-6 px-4 py-10">
      <div className="flex flex-col items-center gap-2 text-center">
        {/* eslint-disable-next-line @next/next/no-img-element -- static SVG brand mark */}
        <img src="/logo.svg" alt="" className="size-10" />
        <h1 className="text-xl font-medium">Sign in to Diarist</h1>
        <p className="text-sm text-muted-foreground">Your recordings and transcripts, in your own workspace.</p>
      </div>
      <SignIn path="/sign-in" routing="path" signUpUrl="/sign-up" />
    </main>
  );
}
