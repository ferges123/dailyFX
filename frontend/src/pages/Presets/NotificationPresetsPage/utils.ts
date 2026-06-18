export function getPushDiagnostics(
  webPushSupport: {
    hasNotification: boolean;
    hasServiceWorker: boolean;
    hasPushManager: boolean;
    isSecureContext: boolean;
  },
  notificationPermission: string,
) {
  let diagnosticsText = '';
  let diagnosticsColor = 'text-stone-500 bg-stone-100 border-stone-200';
  let showPermissionButton = false;

  if (
    !webPushSupport.hasNotification ||
    !webPushSupport.hasServiceWorker ||
    !webPushSupport.hasPushManager
  ) {
    diagnosticsText = 'This browser does not support Web Push';
    diagnosticsColor = 'text-rose-700 bg-rose-50 border-rose-200';
  } else if (!webPushSupport.isSecureContext) {
    diagnosticsText = 'Web Push requires HTTPS or a local localhost context';
    diagnosticsColor = 'text-amber-700 bg-amber-50 border-amber-200';
  } else if (notificationPermission === 'default') {
    diagnosticsText = 'Requires permission';
    diagnosticsColor = 'text-amber-700 bg-amber-50 border-amber-200';
    showPermissionButton = true;
  } else if (notificationPermission === 'denied') {
    diagnosticsText = 'Blocked in browser settings';
    diagnosticsColor = 'text-rose-700 bg-rose-50 border-rose-200';
  } else if (notificationPermission === 'granted') {
    diagnosticsText = 'Notifications enabled';
    diagnosticsColor = 'text-emerald-700 bg-emerald-50 border-emerald-200';
  }

  return { diagnosticsText, diagnosticsColor, showPermissionButton };
}
