"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import Terminal from "@/components/terminal";
export default function Page() {
  const [client] = useState(() => new QueryClient());
  return <QueryClientProvider client={client}><Terminal /></QueryClientProvider>;
}
