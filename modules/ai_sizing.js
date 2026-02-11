/**
 * AI Sizing Module 
 * Handles camera integration and size estimation
 */

import { apiService } from './api_service.js';

export function initAiSizing() {
    console.log('AI Sizing Module: Initializing...');

    const btn = document.getElementById('start-scan-btn');
    if (btn) {
        btn.onclick = () => {
            console.log("Start scan clicked");
            alert("AI Scanning feature coming soon!");
        };
    }
}
