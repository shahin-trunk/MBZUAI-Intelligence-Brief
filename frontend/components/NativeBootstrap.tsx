"use client";

import { useEffect } from "react";

export function NativeBootstrap() {
  useEffect(() => {
    async function boot() {
      const { initNative } = await import("@/lib/native/init");
      await initNative();

      const { initPushNotifications } = await import(
        "@/lib/native/push-notifications"
      );
      await initPushNotifications();
    }
    boot();
  }, []);

  return null;
}
