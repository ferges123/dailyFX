# Home Assistant Notifications Setup for DailyFX for immich

The Home Assistant integration lets DailyFX send notifications about newly generated images directly to your smart home system through the official Home Assistant API.

---

## Step 1: Create a Home Assistant access token

You need a long-lived access token (LLAT) for authentication.

1. Log in to your **Home Assistant** dashboard.
2. Click your profile in the lower-left corner.
3. Scroll to the **Long-Lived Access Tokens** section.
4. Click **Create Token**.
5. Give the token a name, for example `DailyFX Notifier`, and confirm.
6. Copy the token and store it safely. You will not be able to view it again.

---

## Step 2: Find the notification service name

Home Assistant can send notifications to different targets, such as a phone with the HA Companion app, a media player, or a speaker.

1. In Home Assistant, open **Developer Tools** and then the **Services** tab.
2. Search for `notify.`.
3. Pick the service you want to use, for example:
   - `notify.notify` for the default notification channel
   - `notify.mobile_app_your_phone` for a specific device
4. Keep only the part after `notify.`. That value becomes your **Notifier Service Name**.

---

## Step 3: Configure DailyFX

1. Open the **DailyFX for immich** web UI.
2. Go to **Presets** -> **Notifications**.
3. Click **New preset**.
4. Enter any name, for example `Home Assistant`.
5. Enable the **Home Assistant** channel.
6. Fill in the fields:
   - **Server URL**: Your Home Assistant URL, including port if needed, for example `http://192.168.1.100:8123` or `https://your-ha.example.com`
   - **Notifier Service Name**: The service name without the `notify.` prefix, for example `mobile_app_your_phone`, or leave it empty to use the default `notify`
   - **Home Assistant Access Token (LLAT)**: Paste the token you created earlier
7. Click **Save**.
8. Click **Test** next to the new preset and verify that the test notification arrives.

---

## Useful tips

### Persistent notifications in the Home Assistant sidebar
If you want notifications to appear in the Home Assistant UI instead of on a device, set **Notifier Service Name** to:

```text
persistent_notification
```

This makes DailyFX call `notify.persistent_notification` and create a persistent notification in Home Assistant.

### Preview images and action buttons
To show image previews and action buttons in Home Assistant notifications, set **`APP_EXTERNAL_URL`** in your `.env` file:

1. Open `.env`.
2. Add your external or local DailyFX URL:

```env
APP_EXTERNAL_URL=http://192.168.1.100:8439
```

3. Restart the containers:

```bash
docker compose up -d
```

After that, notifications can include a preview image and a link back to the review page.
