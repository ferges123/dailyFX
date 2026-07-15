export function appendQueryParam(
  url: string,
  name: string,
  value: string,
): string {
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${encodeURIComponent(name)}=${encodeURIComponent(value)}`;
}
