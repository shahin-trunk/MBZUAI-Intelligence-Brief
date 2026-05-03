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
  },
  android: {
    allowMixedContent: false,
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
  },
};

export default config;
