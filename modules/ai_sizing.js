import { calculateMeasurements } from './api_service.js';
import { auth } from './firebase_config.js';
import { saveMeasurements } from './db_service.js';

let isScanning = false;
let frontImage = null;
let sideImage = null;
let frontFileInput = null;
let sideFileInput = null;

export function initAiSizing() {
    // AI Sizing Module initialized


    const startBtn = document.getElementById('start-scan-btn');
    const scanResults = document.getElementById('scan-results');
    const scannerUI = document.querySelector('.scanner-ui');
    const container = document.querySelector('.ai-container');

    if (!startBtn) return;

    // Create dual file inputs for front and side photos
    if (!frontFileInput) {
        frontFileInput = document.createElement('input');
        frontFileInput.type = 'file';
        frontFileInput.id = 'ai-front-upload';
        frontFileInput.accept = 'image/*';
        frontFileInput.style.display = 'none';
        document.body.appendChild(frontFileInput);
    }

    if (!sideFileInput) {
        sideFileInput = document.createElement('input');
        sideFileInput.type = 'file';
        sideFileInput.id = 'ai-side-upload';
        sideFileInput.accept = 'image/*';
        sideFileInput.style.display = 'none';
        document.body.appendChild(sideFileInput);
    }

    // Clone button to remove old listeners
    const newBtn = startBtn.cloneNode(true);
    startBtn.parentNode.replaceChild(newBtn, startBtn);

    newBtn.addEventListener('click', () => {
        if (isScanning) return;
        showDualUploadUI(scannerUI);
    });
}

// Function to show dual upload UI
function showDualUploadUI(scannerUI) {
    frontImage = null;
    sideImage = null;

    scannerUI.innerHTML = `
        <div class="dual-upload-container animated-entry">
            <span class="material-icons-round huge-icon" style="color:var(--primary); margin-bottom:20px;">add_photo_alternate</span>
            <h3>Upload Your Photos</h3>
            <p>For best accuracy, provide both front and side view photos</p>
            
            <div class="upload-slots" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 30px 0;">
                <div class="upload-slot" id="front-slot" style="border: 2px dashed var(--border); border-radius: 12px; padding: 30px; text-align: center; cursor: pointer; transition: all 0.3s;">
                    <span class="material-icons-round" style="font-size: 48px; color: var(--text-secondary);">person</span>
                    <h4 style="margin: 10px 0 5px;">Front View</h4>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;">Required</p>
                    <div class="preview-container" id="front-preview" style="display: none; margin-top: 10px;">
                        <img id="front-img" style="max-width: 100%; max-height: 150px; border-radius: 8px;" />
                        <p style="color: var(--success); font-size: 12px; margin-top: 5px;">✓ Uploaded</p>
                    </div>
                </div>
                
                <div class="upload-slot" id="side-slot" style="border: 2px dashed var(--border); border-radius: 12px; padding: 30px; text-align: center; cursor: pointer; transition: all 0.3s;">
                    <span class="material-icons-round" style="font-size: 48px; color: var(--text-secondary);">accessibility</span>
                    <h4 style="margin: 10px 0 5px;">Side View</h4>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;">Optional (for better accuracy)</p>
                    <div class="preview-container" id="side-preview" style="display: none; margin-top: 10px;">
                        <img id="side-img" style="max-width: 100%; max-height: 150px; border-radius: 8px;" />
                        <p style="color: var(--success); font-size: 12px; margin-top: 5px;">✓ Uploaded</p>
                    </div>
                </div>
            </div>
            
            <button class="btn-primary full-width" id="continue-to-height-btn" style="margin-top: 20px;" disabled>
                Continue
            </button>
            <button class="btn-text" id="cancel-upload-btn" style="margin-top: 10px;">Cancel</button>
        </div>
    `;

    const frontSlot = document.getElementById('front-slot');
    const sideSlot = document.getElementById('side-slot');
    const continueBtn = document.getElementById('continue-to-height-btn');
    const cancelBtn = document.getElementById('cancel-upload-btn');

    // Front slot click
    frontSlot.onclick = () => {
        frontFileInput.value = '';
        frontFileInput.click();
    };

    // Side slot click
    sideSlot.onclick = () => {
        sideFileInput.value = '';
        sideFileInput.click();
    };

    // Front image change
    frontFileInput.onchange = (e) => {
        if (e.target.files && e.target.files[0]) {
            frontImage = e.target.files[0];
            const reader = new FileReader();
            reader.onload = (event) => {
                const img = document.getElementById('front-img');
                if (img) img.src = event.target.result;
                const preview = document.getElementById('front-preview');
                if (preview) preview.style.display = 'block';
                frontSlot.style.borderColor = 'var(--success)';
                frontSlot.style.backgroundColor = 'rgba(34, 197, 94, 0.05)';
            };
            reader.readAsDataURL(frontImage);
            continueBtn.disabled = false;
        }
    };

    // Side image change
    sideFileInput.onchange = (e) => {
        if (e.target.files && e.target.files[0]) {
            sideImage = e.target.files[0];
            const reader = new FileReader();
            reader.onload = (event) => {
                const img = document.getElementById('side-img');
                if (img) img.src = event.target.result;
                const preview = document.getElementById('side-preview');
                if (preview) preview.style.display = 'block';
                sideSlot.style.borderColor = 'var(--success)';
                sideSlot.style.backgroundColor = 'rgba(34, 197, 94, 0.05)';
            };
            reader.readAsDataURL(sideImage);
        }
    };

    // Continue button - show height input
    continueBtn.onclick = () => {
        if (!frontImage) {
            if (window.app && window.app.showToast) window.app.showToast("Please upload at least a front view photo", 'error');
            return;
        }
        showHeightInput(scannerUI);
    };

    // Cancel button
    cancelBtn.onclick = () => {
        location.reload();
    };
}

// Function to show height input after photos are uploaded
function showHeightInput(scannerUI) {
    const container = document.querySelector('.ai-container');
    scannerUI.innerHTML = `
            <div class="height-input-container animated-entry">
                <span class="material-icons-round huge-icon" style="color:var(--primary); margin-bottom:20px;">straighten</span>
                <h3>One Last Thing</h3>
                <p>We need your height to calibrate the measurements precisely.</p>
                
                <div class="input-group" style="max-width: 300px; margin: 0 auto;">
                    <input type="number" id="user-height-input" placeholder="Height in CM (e.g. 175)" style="text-align:center;">
                </div>

                <button class="btn-primary full-width" id="confirm-height-btn" style="margin-top:20px;">
                    Start Analysis
                </button>
                <button class="btn-text" id="cancel-scan-btn" style="margin-top:10px;">Cancel</button>
            </div>
        `;

    // Handle Input Logic
    const confirmBtn = document.getElementById('confirm-height-btn');
    const cancelBtn = document.getElementById('cancel-scan-btn');
    const heightInput = document.getElementById('user-height-input');

    // Focus input
    setTimeout(() => { if (heightInput) heightInput.focus(); }, 100);

    cancelBtn.onclick = () => {
        location.reload();
    };

    confirmBtn.onclick = async () => {
        const heightVal = heightInput.value;
        if (!heightVal || isNaN(heightVal) || heightVal < 50 || heightVal > 300) {
            if (window.app && window.app.showToast) window.app.showToast("Please enter a valid height (50-300cm).", 'error');
            return;
        }

        // 2. SHOW LOADING STATE
        isScanning = true;
        scannerUI.innerHTML = `
                <div class="loader"></div>
                <h3>Scanning...</h3>
                <p>Analyzing body proportions with AI...</p>
            `;

        // Visualize Scan Line
        const scanLine = document.querySelector('.scan-line');
        if (scanLine) scanLine.classList.add('scanning-active');

        try {
            // 3. CALL LOCAL API with both images
            // Uploading to Python Server...
            const data = await calculateMeasurements(frontImage, sideImage, parseFloat(heightVal));

            // SAVE TO FIREBASE
            if (auth.currentUser) {
                saveMeasurements(auth.currentUser.uid, data).catch(err => {
                    // Silent fail for measurements save - user already has results
                });
            }

            displayResults(data, scannerUI, container);
            isScanning = false;

        } catch (error) {
            console.error("AI Error:", error);
            isScanning = false;

            let errorMsg = "Scanning Failed. Is the Python server running?";
            if (error.message && (error.message.includes("Failed to fetch") || error.message.includes("NetworkError"))) {
                errorMsg = "❌ Connection Refused. Please run 'python app.py' locally.";
            } else {
                errorMsg = error.message;
            }

            scannerUI.innerHTML = `
                    <span class="material-icons-round huge-icon" style="color: #ef4444">error_outline</span>
                    <h3>Scan Failed</h3>
                    <p>${errorMsg}</p>
                    <button class="btn-primary" onclick="location.reload()">Try Again</button>
                    <small style="display:block; margin-top:10px; opacity:0.6; font-size:11px;">${error.message}</small>
                `;
        }
    };
}

// Make function globally available so onclick works
window.app = window.app || {};

function displayResults(data, ui, container) {
    // SANITY CHECK: Validate anatomical plausibility
    const chest = data.chest_circumference || data.chest || 0;
    const waist = data.waist || data.waist_circumference || 0;
    const hip = data.hip || data.hip_circumference || 0;

    // improved size calculation
    let size = "M";
    if (chest > 0) {
        if (chest < 86) size = "XS";
        else if (chest <= 93) size = "S";
        else if (chest <= 103) size = "M";
        else if (chest <= 111) size = "L";
        else if (chest <= 119) size = "XL";
        else if (chest <= 129) size = "XXL";
        else size = "3XL";

        if (waist > 0) {
            const ratio = chest / waist;
            if (ratio < 1.05 && size !== "3XL") {
                const sizes = ["XS", "S", "M", "L", "XL", "XXL", "3XL"];
                const currentIndex = sizes.indexOf(size);
                if (currentIndex < sizes.length - 1) {
                    size = sizes[currentIndex + 1];
                }
            }
        }
    }

    // Determine Body Type
    let bodyType = "Regular";
    if (chest > 0 && waist > 0) {
        const ratio = chest / waist;
        if (ratio > 1.3) bodyType = "Athletic";
        else if (ratio < 1.1) bodyType = "Slim";
        else bodyType = "Regular";
    }

    // Calculate confidence score
    const measurements = [
        data.chest_circumference, data.waist, data.hip,
        data.shoulder_width, data.arm_length, data.trouser_length,
        data.thigh, data.neck
    ];
    const validCount = measurements.filter(m => m && m > 0).length;
    const confidence = Math.min(98, Math.round((validCount / measurements.length) * 100));

    if (ui) ui.style.display = 'none';

    // Helper to safely format numbers
    const fmt = (val) => (val && val > 0) ? val.toFixed(1) : 'N/A';
    const fmtWithUnit = (val) => (val && val > 0) ? `${val.toFixed(1)} <span class="unit">cm</span>` : '<span style="color: var(--text-secondary); font-size: 0.9em;">Not detected</span>';

    const resultsHTML = `
        <div class="ai-results-premium glass-panel animated-entry">
            <!-- Hero Section -->
            <div class="size-hero">
                <h2 class="gradient-text">Your Perfect Fit</h2>
                <div class="size-badge-huge">${size}</div>
                <p class="based-on">Based on ${validCount} detected measurement points</p>
                
                <!-- Confidence Score -->
                <div class="confidence-container">
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${confidence}%"></div>
                    </div>
                    <span class="confidence-text">${confidence}% Match Confidence</span>
                </div>
            </div>

            <!-- Measurements Grid -->
            <div class="measurements-section">
                <h3 class="section-title">
                    <span class="material-icons-round">straighten</span>
                    Detailed Measurements
                </h3>
                
                <div class="measurements-grid-premium">
                    <!-- Upper Body -->
                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">checkroom</span>
                        <div class="m-content">
                            <label>Chest</label>
                            <strong>${fmtWithUnit(data.chest_circumference || data.chest)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">accessibility</span>
                        <div class="m-content">
                            <label>Waist</label>
                            <strong>${fmtWithUnit(data.waist || data.waist_circumference)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">fitness_center</span>
                        <div class="m-content">
                            <label>Hips</label>
                            <strong>${fmtWithUnit(data.hip || data.hip_circumference)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">height</span>
                        <div class="m-content">
                            <label>Shoulder</label>
                            <strong>${fmtWithUnit(data.shoulder_width || data.shoulder)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">back_hand</span>
                        <div class="m-content">
                            <label>Arm Length</label>
                            <strong>${fmtWithUnit(data.arm_length)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">straighten</span>
                        <div class="m-content">
                            <label>Inseam</label>
                            <strong>${fmtWithUnit(data.trouser_length)}</strong>
                        </div>
                    </div>

                    <!-- Additional Measurements -->
                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">sports_martial_arts</span>
                        <div class="m-content">
                            <label>Thigh</label>
                            <strong>${fmtWithUnit(data.thigh || data.thigh_circumference)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">face</span>
                        <div class="m-content">
                            <label>Neck</label>
                            <strong>${fmtWithUnit(data.neck)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">straighten</span>
                        <div class="m-content">
                            <label>Shirt Length</label>
                            <strong>${fmtWithUnit(data.shirt_length || data.torso_length)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">directions_walk</span>
                        <div class="m-content">
                            <label>Leg Length</label>
                            <strong>${fmtWithUnit(data.leg_length || data.trouser_length)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">sports</span>
                        <div class="m-content">
                            <label>Bicep</label>
                            <strong>${fmtWithUnit(data.bicep)}</strong>
                        </div>
                    </div>

                    <div class="measurement-card">
                        <span class="material-icons-round m-icon">sports_gymnastics</span>
                        <div class="m-content">
                            <label>Calf</label>
                            <strong>${fmtWithUnit(data.calf)}</strong>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="ai-actions-premium">
                <button class="btn-primary gradient-btn full-width glow-on-hover" onclick="window.app.navigateTo('custom-design')">
                    <span class="material-icons-round">brush</span>
                    Start Designing
                </button>
                <div class="secondary-actions">
                    <button class="btn-outline" id="redo-scan-btn">
                        <span class="material-icons-round">refresh</span>
                        Redo Scan
                    </button>
                    <button class="btn-outline" id="export-measurements-btn">
                        <span class="material-icons-round">download</span>
                        Export Record
                    </button>
                </div>
            </div>
        </div>
    `;

    const resultsDiv = document.getElementById('scan-results');
    resultsDiv.innerHTML = resultsHTML;
    resultsDiv.classList.remove('hidden');
    resultsDiv.style.display = 'block';

    // Bind redo listener
    document.getElementById('redo-scan-btn').onclick = () => {
        resultsDiv.innerHTML = '';
        resultsDiv.style.display = 'none';

        if (ui) {
            ui.style.display = 'flex';
            showDualUploadUI(ui);
        }
    };

    // Export functionality
    document.getElementById('export-measurements-btn').onclick = () => {
        try {
            const pdfContent = `
YOUNGIN - Body Measurements Report
${'='.repeat(50)}

Recommended Size: ${size}
Body Type: ${bodyType} Build
Confidence Score: ${confidence}%

Detailed Measurements:
${'-'.repeat(50)}
Chest: ${fmt(data.chest_circumference || data.chest)} cm
Waist: ${fmt(data.waist || data.waist_circumference)} cm
Hips: ${fmt(data.hip || data.hip_circumference)} cm
Shoulder: ${fmt(data.shoulder_width || data.shoulder)} cm
Arm Length: ${fmt(data.arm_length)} cm
Inseam: ${fmt(data.trouser_length)} cm
Thigh: ${fmt(data.thigh || data.thigh_circumference)} cm
Neck: ${fmt(data.neck || 0)} cm
Shirt Length: ${fmt(data.shirt_length || data.torso_length)} cm
Leg Length: ${fmt(data.leg_length || data.trouser_length)} cm
Bicep: ${fmt(data.bicep || 0)} cm
Calf: ${fmt(data.calf || 0)} cm

Generated: ${new Date().toLocaleString()}
YOUNGIN.com - Custom Clothing Design
            `;

            const blob = new Blob([pdfContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `YOUNGIN_Measurements_${size}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            const btn = document.getElementById('export-measurements-btn');
            btn.innerHTML = '<span class="material-icons-round">check</span> Downloaded!';
            setTimeout(() => {
                btn.innerHTML = '<span class="material-icons-round">download</span> Export Record';
            }, 2000);
        } catch (error) {
            console.error('Export error:', error);
            if (window.app && window.app.showToast) window.app.showToast('Export failed', 'error');
        }
    };
}
