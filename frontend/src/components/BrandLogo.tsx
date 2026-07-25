const BRAND_LOGO = '/pwa-192x192.png';

export function BrandLogo({ className }: { className: string }) {
  return (
    <img
      src={BRAND_LOGO}
      alt="DailyFX logo"
      width={192}
      height={192}
      className={`${className} shrink-0 rounded-xl object-cover shadow-[0_10px_22px_rgba(36,29,16,0.16)]`}
    />
  );
}
