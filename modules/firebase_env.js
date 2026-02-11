/**
 * Firebase Environment Configuration
 * This file contains the actual Firebase config and should be gitignored for local development
 * For production (Vercel), these values will be injected via environment variables
 */

// For local development, set your Firebase config here
// For production, this will be replaced by build-time environment variables
export const firebaseConfig = {
    apiKey: "AIzaSyByfQ2r8O7WsC29mnU_g9aEbQkuVAA-rPI",
    authDomain: "youngin-fb727.firebaseapp.com",
    projectId: "youngin-fb727",
    storageBucket: "youngin-fb727.firebasestorage.app",
    messagingSenderId: "17128404672",
    appId: "1:17128404672:web:2de20021f2830faa87df25",
    measurementId: "G-PSNCJB9072"
};

// Note: Firebase API keys are safe to expose in client-side code
// They are not secret keys - Firebase uses Security Rules for data protection
// This separation is mainly for organization and deployment flexibility
