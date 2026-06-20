const BRAND_LOGO_LIGHT = '/logo_light.png';

export function BrandLogo({ className }: { className: string }) {
  return (
    <img
      src={BRAND_LOGO_LIGHT}
      alt="DailyFX logo"
      className={`${className} shrink-0 rounded-xl object-cover shadow-[0_10px_22px_rgba(36,29,16,0.16)]`}
    />
  );
}
