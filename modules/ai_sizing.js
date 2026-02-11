/**
 * AI Sizing Module 
 * Handles camera integration and size estimation
 */

import { apiService } from './api_service.js';

export function initAiSizing() {
    console.log('AI Sizing Module: Initializing...');

    const btn = document.getElementById('start-scan-btn');
    const resultContainer = document.getElementById('scan-results');

    if (btn) {
        btn.onclick = async () => {
            console.log("Start scan clicked");
            btn.innerText = "Scanning...";
            btn.disabled = true;

            try {
                // Simulate camera capture (would be real in prod)
                const mockImage = "data:image/jpeg;base64,.....";

                const measurements = await apiService.uploadForSizing(mockImage);

                if (measurements) {
                    displayResults(measurements);
                }
            } catch (error) {
                console.error("Scan failed", error);
                alert("Scan failed. Please try again.");
                btn.innerText = "Upload Photo";
                btn.disabled = false;
            }
        };
    }
}

function displayResults(data) {
    const container = document.getElementById('scan-results');
    if (container) {
        container.innerHTML = `
            <div class="results-card">
                <h4>Your Measurements</h4>
                <p>Height: ${data.height} cm</p>
                <p>Chest: ${data.chest} cm</p>
                <p>Waist: ${data.waist} cm</p>
            </div>
        `;
        container.classList.remove('hidden');
    }
}
