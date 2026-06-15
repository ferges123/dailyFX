# Design: Telegram Notification Review Page Link Button

## Overview
Currently, Telegram inline keyboard buttons sent with notifications only contain "Accept & Upload" and "Reject" buttons. This design introduces a third button, "Review", in the same row, which links directly to the generation review page on the application.

Furthermore, we will rename "✅ Accept & Upload" to "✅ Accept" to keep the buttons clean and compact on the same row.

## Design Details
1. **Button Row Layout**:
   - The button row will look as follows:
     `[ ✅ Accept ]` `[ ❌ Reject ]` `[ 🔍 Review ]`
   - The "Review" button will only be displayed if `review_url` is provided (which relies on `app_external_url` being configured in the application settings).
   
2. **Backend Code Changes**:
   - **`backend/app/notifications/providers/telegram.py`**:
     - Update `send_telegram_notification` parameter list to include `review_url: str | None = None`.
     - In the button definition, rename `Accept & Upload` to `Accept`.
     - Append `{"text": "🔍 Review", "url": review_url}` to the list of buttons if `review_url` is provided.
   - **`backend/app/services/generation/output.py`**:
     - Pass `review_url=abs_app_url` to `send_telegram_notification`.

3. **Test Code Changes**:
   - **`backend/tests/test_notifications.py`**:
     - Update the unit tests to mock and assert the new button texts and the presence of the `Review` button when `review_url` is supplied.

## Risks & Considerations
- If `app_external_url` is not set, `abs_app_url` is `None`. In this case, the `Review` button will not be displayed, and only the `Accept` and `Reject` buttons will be present. This is the desired fallback behavior.
