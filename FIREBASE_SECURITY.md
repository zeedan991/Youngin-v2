# Firebase Configuration & Security

## About Firebase API Keys

**Important**: Firebase API keys in client-side code are **NOT secret keys**. They are safe to expose publicly because:

1. **Firebase uses Security Rules**, not API key secrecy, to protect your data
2. The API key only identifies your Firebase project
3. Access control is enforced through Firestore Security Rules and Firebase Authentication

## GitHub Security Alert

If you received a GitHub security alert about an exposed Google API Key in `modules/firebase_config.js`, you can safely dismiss it or mark it as "Won't fix" because:

- Firebase API keys are meant to be public in client-side apps
- Your data is protected by Firebase Security Rules (set in Firebase Console)
- The API key cannot be used maliciously without proper authentication

## Project Setup

### Current Configuration

The Firebase config has been moved to `modules/firebase_env.js` for better organization. The actual API key is included in this file.

### For Vercel Deployment

This project is configured to work seamlessly with Vercel. No additional environment variables needed since Firebase API keys are safe to include in the codebase.

### Security Best Practices

1. **Firestore Security Rules**: Ensure your Firestore rules require authentication
2. **Firebase Authentication**: All sensitive operations require users to be logged in
3. **API Key Restrictions** (Optional): You can add HTTP referrer restrictions in Firebase Console under Project Settings > API Keys

## Resolving the GitHub Alert

To close the GitHub security alert:

1. Go to your repository's Security tab
2. Click on "Secret scanning alerts"
3. Select the alert about the Google API Key
4. Click "Dismiss alert"
5. Choose reason: "Used in tests" or "Won't fix"
6. Add note: "Firebase API keys are safe to expose - data is protected by Security Rules"

Alternatively, you can:
- Create a new Firebase API key in the Firebase Console
- Update `firebase_env.js` with the new key
- Commit the change (this will close the alert automatically)
