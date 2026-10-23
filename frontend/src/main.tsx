import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { PrivacyCenter } from "./Privacy";
import { AppUpdateNotice } from "./AppUpdateNotice";
import "./styles.css";
import "./billing/styles.css";

const client = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <AppUpdateNotice />
      <div id="privacy-banner" />
      <App />
      <PrivacyCenter />
    </QueryClientProvider>
  </React.StrictMode>,
);
