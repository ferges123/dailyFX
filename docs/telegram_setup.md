# Telegram Bot Notifications Setup for DailyFX for immich

The Telegram integration lets DailyFX send a preview of newly generated images directly to your phone, with interactive **Accept & Upload** and **Reject** buttons.

---

## Step 1: Create a Telegram bot

1. Open Telegram and find **@BotFather**.
2. Send the `/newbot` command.
3. Give your bot a display name, for example `DailyFX Notifier`.
4. Pick a unique username that ends with `bot`, for example `my_dailyfx_bot`.
5. When BotFather finishes, it will send you an **API token**. Save it. This is your **Telegram Bot Token**.

---

## Step 2: Find your Chat ID

The bot needs to know where to send messages. That can be a private chat, group, or channel.

### Option A: Private chat
1. Find your bot by username, for example `@my_dailyfx_bot`, and tap **Start**.
2. Find **@userinfobot** in Telegram and send it any message.
3. The bot will reply with your user ID. That number is your **Telegram Chat ID**.

### Option B: Group or channel
1. Create a group or channel.
2. Add your bot to it, and make it an admin if it is a channel.
3. Send a test message in the group or channel.
4. Open this URL in a browser, replacing `<BOT_TOKEN>` with your bot token:

```text
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```

5. Find the `"chat"` object in the JSON response and copy the `"id"` value. That is your **Telegram Chat ID**.

---

## Step 3: Configure DailyFX

1. Open the **DailyFX for immich** web UI.
2. Go to **Presets** -> **Notifications**.
3. Click **New preset**.
4. Enter any name, for example `Telegram Notifications`.
5. Enable the **Telegram** channel.
6. Fill in the fields:
   - **Telegram Chat ID**: The chat ID you found earlier, for example `987654321` or `-100123456789`
   - **Telegram Bot Token**: Your bot token
7. Click **Save**.
8. Click **Test** next to the preset and verify that the test notification arrives.

---

## Step 4: Interactive buttons

When this preset is attached to a schedule and generation completes successfully:

1. You will receive a Telegram message with a preview image and buttons:
   - `✅ Accept & Upload` uploads the generated image to Immich
   - `❌ Reject` rejects the image and deletes the temporary file
2. After you click a button, the bot updates the message to show the new status and removes the buttons so the action cannot be repeated.
