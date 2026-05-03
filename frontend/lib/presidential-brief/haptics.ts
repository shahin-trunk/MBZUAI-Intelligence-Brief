export async function hapticImpact(style: "light" | "medium" | "heavy" = "medium") {
  // Will use Capacitor Haptics plugin when native shell is added
  if (process.env.NODE_ENV === "development") {
    console.log(`[haptic] impact: ${style}`);
  }
}

export async function hapticSelection() {
  if (process.env.NODE_ENV === "development") {
    console.log("[haptic] selection");
  }
}
