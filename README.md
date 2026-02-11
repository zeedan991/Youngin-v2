# YOUNGIN.v2 - Frontend

The premium frontend for YOUNGIN, a next-gen custom clothing design platform. Built with vanilla JavaScript, HTML5, and CSS3 for maximum performance and design flexibility.

## 🚀 Features

- **AI Body Sizing**: Dual-photo measurement system with Ramanujan's formula for high accuracy.
- **3D Customizer**: Interactive T-shirt design tool using Three.js (planned).
- **Virtual Try-On**: Augmented reality fitting room.
- **AI Chatbot**: Gemini-powered fashion assistant for style advice and support.
- **Local Tailor Hub**: Connect with premium tailors in your area.
- **Rich & Rare**: Exclusive luxury marketplace with VIP access.

## 🛠️ Tech Stack

- **Core**: HTML5, CSS3, JavaScript (ES6+)
- **Styling**: Custom CSS variables, Glassmorphism design system
- **State Management**: Specialized modules (`cart.js`, `profile.js`, `firebase_config.js`)
- **Backend Integration**: Proxied requests to Python/Flask backend via Vercel
- **Authentication**: Firebase Auth (Google & Email/Password)
- **Database**: Firebase Firestore

## 📂 Project Structure

```
Youngin.v2/
├── modules/                 # Functional modules
│   ├── ai_sizing.js        # AI Measurement logic
│   ├── api_service.js      # Backend API communication
│   ├── cart.js             # Shopping cart management
│   ├── chatbot.js          # AI Chatbot interface
│   ├── custom_design.js    # 3D/Canvas design tool
│   ├── firebase_config.js  # Auth & DB configuration
│   ├── marketplace.js      # Product listing & filtering
│   ├── profile.js          # User profile & order history
│   └── social_local.js     # Tailor hub & Luxury market
├── assets/                 # Images and icons
├── index.html              # Main entry point
├── script.js               # Global app controller & router
├── style.css               # Global styles & design system
└── vercel.json             # Deployment configuration
```

## 🔧 Setup & Development

1. **Install Dependencies** (optional, for local server):
   ```bash
   npm install -g live-server
   ```

2. **Run Locally**:
   ```bash
   live-server
   ```

3. **Backend Connection**:
   - The frontend communicates with the backend via `/api/*` routes.
   - locally, ensure your `vercel.json` rewrites or local proxy is set up.
   - Production points to: `https://zedaan-youngin-backend-v2.hf.space`

## 📦 Deployment

This project is configured for **Vercel**.

1. **Push to GitHub**:
   ```bash
   git push origin master
   ```
2. **Vercel** will automatically detect the commit and deploy.
3. **Environment**: Ensure Firebase config is set up in `modules/firebase_config.js`.

## 🎨 Design System

- **Primary Color**: `#70e1f5` to `#ffd194` (Sunset Gradient)
- **Dark Mode**: Deep Blue/Black backgrounds with glassmorphism overlays
- **Typography**: 'Outfit' (Headings), 'Inter' (Body)

---

&copy; 2024 YOUNGIN. All rights reserved.
