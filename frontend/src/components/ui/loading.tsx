export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <p role="status" className="px-4 py-10 text-center text-sm text-muted-foreground">
      {message}
    </p>
  );
}
