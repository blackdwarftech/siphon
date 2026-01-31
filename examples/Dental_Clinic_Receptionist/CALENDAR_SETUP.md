# Google Calendar Setup Guide

This guide walks you through setting up Google Calendar API credentials for your SIPHON agent.

## Overview

To enable calendar integration, you need:
1. A Google Cloud project
2. Google Calendar API enabled
3. Service account credentials
4. Calendar sharing permissions

## Step-by-Step Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Create Project"** or select an existing project
3. Give your project a name (e.g., "SIPHON Dental Agent")
4. Click **"Create"**

### 2. Enable Google Calendar API

1. In your project, navigate to **"APIs & Services"** → **"Library"**
2. Search for **"Google Calendar API"**
3. Click on it and click **"Enable"**

### 3. Create Service Account

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"Create Credentials"** → **"Service Account"**
3. Enter a name (e.g., "siphon-agent-calendar")
4. Click **"Create and Continue"**
5. Skip optional role assignment (click **"Continue"**)
6. Click **"Done"**

### 4. Generate Service Account Key

1. Click on the newly created service account
2. Go to the **"Keys"** tab
3. Click **"Add Key"** → **"Create new key"**
4. Select **"JSON"** format
5. Click **"Create"** - this downloads the credentials file
6. **Save this file securely** - you'll reference its path in `.env`

### 5. Create or Use Existing Google Calendar

**Option A: Use Gmail Calendar**
- Your default Google Calendar ID is: `your-email@gmail.com`

**Option B: Create New Calendar**
1. Go to [Google Calendar](https://calendar.google.com/)
2. Click the **"+"** next to **"Other calendars"**
3. Select **"Create new calendar"**
4. Name it (e.g., "Dental Appointments")
5. Click **"Create calendar"**
6. Find the Calendar ID:
   - Go to calendar **Settings** → Select your calendar
   - Scroll to **"Integrate calendar"**
   - Copy the **Calendar ID** (looks like: `abc123@group.calendar.google.com`)

### 6. Share Calendar with Service Account

1. In Google Calendar, go to your calendar's **Settings**
2. Scroll to **"Share with specific people or groups"**
3. Click **"Add people and groups"**
4. Paste the **service account email** from step 3
   - Found in the JSON credentials file as `client_email`
   - Looks like: `siphon-agent-calendar@project-id.iam.gserviceaccount.com`
5. Set permissions to **"Make changes to events"**
6. Click **"Send"**

### 7. Configure Environment Variables

Update your `.env` file with:

```env
GOOGLE_CALENDAR_CREDENTIALS_PATH=/absolute/path/to/your/credentials.json
GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
```

**Important:**
- Use the **absolute path** to your credentials JSON file
- Use the **Calendar ID** from step 5

## Troubleshooting

### "Calendar not found" error
- Double-check the Calendar ID in `.env`
- Ensure the service account email was added to calendar sharing

### "Permission denied" error
- Verify the service account has "Make changes to events" permission
- Re-share the calendar with the correct service account email

### "Credentials not found" error
- Verify `GOOGLE_CALENDAR_CREDENTIALS_PATH` points to the correct file
- Use absolute path, not relative path
- Ensure the JSON file is valid and not corrupted

### Events not showing up
- Check timezone settings in both Calendar and `.env`
- Verify the calendar ID matches exactly
- Look for agent logs for specific error messages

## Security Best Practices

✅ **Do:**
- Store credentials file outside of version control
- Use service accounts (not OAuth for user accounts)
- Limit calendar sharing to only necessary service accounts
- Use environment variables for sensitive paths

❌ **Don't:**
- Commit credentials JSON to Git
- Share service account keys publicly
- Use personal Gmail credentials in production
- Hard-code paths or IDs in source code

## Need More Help?

- [Google Calendar API Documentation](https://developers.google.com/calendar/api/guides/overview)
- [Service Account Guide](https://cloud.google.com/iam/docs/service-accounts)
- [SIPHON Documentation](https://siphon.blackdwarf.in/docs)
