import { staticFile } from "remotion";

export const isVideoSrc = (src: string): boolean => {
  const lowered = src.split("?")[0].toLowerCase();
  if (lowered.startsWith("data:video/")) return true;
  return /\.(mp4|webm|mov|m4v)$/.test(lowered);
};

export const resolveSrc = (src: string): string => {
  if (
    src.startsWith("data:") ||
    src.startsWith("http://") ||
    src.startsWith("https://") ||
    src.startsWith("/")
  ) {
    return src;
  }
  return staticFile(src);
};

export const aspectRatioToCss = (
  aspect: "16:9" | "4:3" | "1:1" | "9:16"
): string => {
  switch (aspect) {
    case "16:9":
      return "16 / 9";
    case "4:3":
      return "4 / 3";
    case "1:1":
      return "1 / 1";
    case "9:16":
      return "9 / 16";
  }
};
