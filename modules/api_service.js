
/**
 * API Service Module
 * Handles API requests to the backend
 */

const API_BASE_URL = 'https://youngin-api-v2.onrender.com';

export const apiService = {
    // Upload image for sizing
    uploadForSizing: async (imageData) => {
        console.log("Uploading image for sizing...");
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    height: 180,
                    chest: 95,
                    waist: 82
                });
            }, 2000);
        });
    }
};
