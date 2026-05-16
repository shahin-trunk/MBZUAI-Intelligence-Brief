import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.mbzuai.intel",
  appName: "MBZUAI Intel",
  webDir: "out",
  server: {
    url: "https://www.mbzuai-intel.com",
    cleartext: false,
    allowNavigation: ["*.mbzuai-intel.com", "mbzuai-intel.com", "*.vercel.app"],
  },
  ios: {
    contentInset: "automatic",
    preferredContentMode: "mobile",
    scrollEnabled: true,
    // Capacitor iOS already sets allowsInlineMediaPlayback=true and
    // mediaTypesRequiringUserActionForPlayback=[] in its WKWebView config,
    // enabling TTS audio autoplay without user gesture.
    appendUserAgent: "MBZUAIIntel",
  },
  android: {
    allowMixedContent: false,
    // Android WebView permits autoplay by default; no extra config needed
    // for HTML5 audio TTS playback.
    appendUserAgent: "MBZUAIIntel",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: "#0A0F1C",
      showSpinner: false,
      launchAutoHide: true,
    },
    StatusBar: {
      style: "DARK",
      backgroundColor: "#0A0F1C",
    },
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
    CapacitorHttp: {
      enabled: true,
    },
  },
};

export default config;
