import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="timm.models.layers")

import cv2
import numpy as np
import mediapipe as mp
import torch
from flask import Flask, request, jsonify
from flask_cors import CORS
import torch.nn.functional as F

import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("🚀 Starting Youngin API Server...")

app = Flask(__name__)

# Configure CORS
# SECURITY NOTE: For production, replace "*" with your specific frontend domain
# Example: ALLOWED_ORIGINS = "https://youngin.vercel.app,https://www.youngin.com"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

logger.info("📦 Initializing MediaPipe models...")
mp_pose = mp.solutions.pose
mp_holistic = mp.solutions.holistic
pose = mp_pose.Pose(model_complexity=2)  # Improved accuracy
holistic = mp_holistic.Holistic()  # For refining pose
logger.info("✅ MediaPipe models initialized")

# Constants for measurement calculations
KNOWN_OBJECT_WIDTH_CM = 21.0  # A4 paper width in cm
FOCAL_LENGTH = 600  # Default focal length for camera calibration
DEFAULT_HEIGHT_CM = 152.0  # Default height if not provided (5 feet)
MIN_HEIGHT_CM = 100.0  # Minimum valid height (1 meter)
MAX_HEIGHT_CM = 250.0  # Maximum valid height (2.5 meters)

# Load depth estimation model
def load_depth_model():
    logger.info("🔄 Loading MiDaS depth estimation model...")
    model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
    model.eval()
    logger.info("✅ MiDaS model loaded successfully")
    return model

logger.info("🧠 Loading depth model (this may take a moment on first run)...")
depth_model = load_depth_model()
logger.info("🎉 All models loaded! API is ready to serve requests.")

def calibrate_focal_length(image, real_width_cm, detected_width_px):
    """Dynamically calibrates focal length using a known object."""
    return (detected_width_px * FOCAL_LENGTH) / real_width_cm if detected_width_px else FOCAL_LENGTH



def detect_reference_object(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        focal_length = calibrate_focal_length(image, KNOWN_OBJECT_WIDTH_CM, w)
        scale_factor = KNOWN_OBJECT_WIDTH_CM / w
        return scale_factor, focal_length
    return 0.05, FOCAL_LENGTH

def estimate_depth(image):
    """Uses AI-based depth estimation to improve circumference calculations."""
    input_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) / 255.0
    input_tensor = torch.tensor(input_image, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
    
    # Resize input to match MiDaS model input size
    input_tensor = F.interpolate(input_tensor, size=(384, 384), mode="bilinear", align_corners=False)

    with torch.no_grad():
        depth_map = depth_model(input_tensor)
    
    return depth_map.squeeze().numpy()

def calculate_distance_using_height(landmarks, image_height, user_height_cm):
    """Calculate distance using the user's known height."""
    # Use nose as reference, but add head height above it
    nose_y = landmarks[mp_pose.PoseLandmark.NOSE.value].y * image_height
    
    # Get the lowest foot point
    bottom_foot = max(
        landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y,
        landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y
    ) * image_height
    
    # Estimate full body height in pixels
    # Nose to ankle is approximately 88% of full height (nose is ~10% down from top of head, ankle is ~2% up from floor)
    nose_to_ankle_px = abs(bottom_foot - nose_y)
    
    # Full height = nose_to_ankle / 0.88 (accounting for head above nose and feet below ankle)
    person_height_px = nose_to_ankle_px / 0.88
    
    # Using the formula: distance = (actual_height_cm * focal_length) / height_in_pixels
    distance = (user_height_cm * FOCAL_LENGTH) / person_height_px
    
    # Calculate more accurate scale_factor based on known height
    scale_factor = user_height_cm / person_height_px
    
    logger.info(f"Height calculation: nose_to_ankle={nose_to_ankle_px}px, estimated_full_height={person_height_px}px, scale_factor={scale_factor}")
    
    return distance, scale_factor

def get_width_from_segmentation(segmentation_mask, height_px, center_x, image_width):
    """
    Scan horizontally at a specific height using MediaPipe segmentation mask.
    This is more robust than color thresholding for dark clothing.
    """
    if segmentation_mask is None:
        return 0
    
    # Ensure height_px is within bounds
    mask_height, mask_width = segmentation_mask.shape
    if height_px >= mask_height:
        height_px = mask_height - 1
    
    # Scale center_x to mask coordinates
    center_x_px = int(center_x * mask_width)
    
    # Get horizontal line at the specified height
    horizontal_line = segmentation_mask[height_px, :]
    
    # Find left and right edges starting from center
    # Segmentation mask: values > 0.1 indicate person
    left_edge, right_edge = center_x_px, center_x_px
    
    # Scan from center to left
    for i in range(center_x_px, 0, -1):
        if horizontal_line[i] < 0.1:  # Found background (not person)
            left_edge = i
            break
    
    # Scan from center to right
    for i in range(center_x_px, mask_width):
        if horizontal_line[i] < 0.1:  # Found background (not person)
            right_edge = i
            break
            
    width_px = right_edge - left_edge
    
    # Scale back to original image width
    width_px = int(width_px * (image_width / mask_width))
    
    # If width is unreasonably small, return 0 (will trigger fallback)
    min_width = 0.05 * image_width  # Minimum 5% of image width
    if width_px < min_width:
        return 0
        
    return width_px

def calculate_side_measurements(results, scale_factor, image_width, image_height, user_height_cm=None):
    """
    Extract depth measurements from side view for accurate circumference calculations.
    Returns depth data for chest, waist, and hip.
    In a SIDE/PROFILE view:
    - X-axis = depth (front-to-back of body)
    - Y-axis = vertical position
    """
    landmarks = results.pose_landmarks.landmark
    
    # If user's height is provided, use it to get a more accurate scale factor
    if user_height_cm:
        _, scale_factor = calculate_distance_using_height(landmarks, image_height, user_height_cm)
    
    def pixel_to_cm(value):
        return round(value * scale_factor, 2)
    
    # Get key landmarks
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    
    # In side view, we measure the visible HORIZONTAL span (X-axis) which represents body depth
    # The person is facing sideways, so front-to-back depth is visible as left-right span
    
    # CHEST DEPTH - Measure from front (nose/chest front) to back (spine area)
    # Use the max and min X positions at shoulder height to get full depth
    shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
    
    # For side view, the depth is the horizontal distance visible
    # Take the shoulder with larger x (front of chest) and smaller x (back)
    front_x = max(left_shoulder.x, right_shoulder.x, nose.x)
    back_x = min(left_shoulder.x, right_shoulder.x)
    
    chest_depth_px = abs(front_x - back_x) * image_width
    # Chest depth should be approximately 60-70% of width, add 20% buffer for accuracy
    chest_depth_cm = pixel_to_cm(chest_depth_px) * 1.2
    
    # WAIST DEPTH - Estimate from torso curvature
    # Waist is narrower than chest, typically 80-90% of chest depth
    waist_depth_cm = chest_depth_cm * 0.85
    
    # HIP DEPTH - Similar to chest or slightly larger
    front_hip_x = max(left_hip.x, right_hip.x)
    back_hip_x = min(left_hip.x, right_hip.x)
    hip_depth_px = abs(front_hip_x - back_hip_x) * image_width
    hip_depth_cm = pixel_to_cm(hip_depth_px) * 1.15
    
    return {
        "chest_depth_cm": chest_depth_cm,
        "waist_depth_cm": waist_depth_cm,
        "hip_depth_cm": hip_depth_cm
    }

def calculate_measurements(results, scale_factor, image_width, image_height, depth_map, segmentation_mask=None, user_height_cm=None, side_depth_data=None):
    landmarks = results.pose_landmarks.landmark

    # If user's height is provided, use it to get a more accurate scale factor
    if user_height_cm:
        _, scale_factor = calculate_distance_using_height(landmarks, image_height, user_height_cm)

    def pixel_to_cm(value):
        return round(value * scale_factor, 2)
    
    def calculate_circumference(width_px, depth_ratio=1.0):
        """
        Estimate circumference using width and depth adjustment.
        Using a simplified elliptical approximation: C Γëê 2╧Ç * sqrt((a┬▓ + b┬▓)/2)
        where a is half the width and b is estimated depth
        """
        width_cm = width_px * scale_factor
        estimated_depth_cm = width_cm * depth_ratio * 0.7  # Depth is typically ~70% of width for torso
        half_width = width_cm / 2
        half_depth = estimated_depth_cm / 2
        return round(2 * np.pi * np.sqrt((half_width**2 + half_depth**2) / 2), 2)

    measurements = {}

    # Get key landmarks
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
    left_knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value]
    left_ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    left_ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR.value]

    # SHOULDER WIDTH - Most reliable measurement
    shoulder_width_px = abs(left_shoulder.x - right_shoulder.x) * image_width
    
    # Apply a slight correction factor for shoulders (they're usually detected well)
    shoulder_correction = 1.1  # 10% wider
    shoulder_width_px *= shoulder_correction
    
    measurements["shoulder_width"] = pixel_to_cm(shoulder_width_px)

    # CHEST/BUST MEASUREMENT
    chest_y_ratio = 0.15  # Approximately 15% down from shoulder to hip
    chest_y = left_shoulder.y + (left_hip.y - left_shoulder.y) * chest_y_ratio
    
    chest_correction = 1.08  # 8% wider - more conservative for varied body types
    chest_width_px = abs((right_shoulder.x - left_shoulder.x) * image_width) * chest_correction
    
    if segmentation_mask is not None:
        chest_y_px = int(chest_y * image_height)
        center_x = (left_shoulder.x + right_shoulder.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, chest_y_px, center_x, image_width)
        if detected_width > 0:
            # SAFETY CHECK: Only accept contour width if it's reasonable
            # If detected width is > 1.5x the landmark width, it's likely catching background (chair/shadow)
            landmark_width = abs(right_shoulder.x - left_shoulder.x) * image_width
            if detected_width < landmark_width * 1.5:  # Allow some expansion but clamp explosions
                 chest_width_px = max(chest_width_px, detected_width)
            else:
                 logger.warning(f"Ignored chest contour width {detected_width}px (too large vs {landmark_width}px)")
    
    chest_depth_ratio = 1.0
    if depth_map is not None:
        chest_x = int(((left_shoulder.x + right_shoulder.x) / 2) * image_width)
        chest_y_px = int(chest_y * image_height)
        scale_y = 384 / image_height
        scale_x = 384 / image_width
        chest_y_scaled = int(chest_y_px * scale_y)
        chest_x_scaled = int(chest_x * scale_x)
        if 0 <= chest_y_scaled < 384 and 0 <= chest_x_scaled < 384:
            chest_depth = depth_map[chest_y_scaled, chest_x_scaled]
            max_depth = np.max(depth_map)
            chest_depth_ratio = 1.0 + 0.5 * (1.0 - chest_depth / max_depth)
    
    measurements["chest_width"] = pixel_to_cm(chest_width_px)
    measurements["chest_circumference"] = calculate_circumference(chest_width_px, chest_depth_ratio)

    # WAIST MEASUREMENT
    # Adjust waist_y_ratio to better reflect the natural waistline
    waist_y_ratio = 0.35  # 35% down from shoulder to hip (higher than before)
    waist_y = left_shoulder.y + (left_hip.y - left_shoulder.y) * waist_y_ratio
    
    # Use contour detection to dynamically estimate waist width
    if segmentation_mask is not None:
        waist_y_px = int(waist_y * image_height)
        center_x = (left_hip.x + right_hip.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, waist_y_px, center_x, image_width)
        
        # Calculate expected width from landmarks for safety check
        hip_landmark_width = abs(right_hip.x - left_hip.x) * image_width
        
        if detected_width > 0 and detected_width < hip_landmark_width * 1.5:
             # If valid and reasonable, use it
             waist_width_px = detected_width
        else:
             logger.warning(f"Ignored waist contour width {detected_width}px (unreasonable)")
             # Fallback to hip width if contour detection fails or is unsafe
             waist_width_px = hip_landmark_width * 0.9  # 90% of hip width
    else:
        # Fallback to hip width if no frame is provided
        waist_width_px = abs(right_hip.x - left_hip.x) * image_width * 0.9  # 90% of hip width
    
    # Apply correction factor to waist width
    waist_correction = 1.05  # 5% wider - more conservative for varied body types
    waist_width_px *= waist_correction
    
    # Get depth adjustment for waist if available
    waist_depth_ratio = 1.0
    if depth_map is not None:
        waist_x = int(((left_hip.x + right_hip.x) / 2) * image_width)
        waist_y_px = int(waist_y * image_height)
        scale_y = 384 / image_height
        scale_x = 384 / image_width
        waist_y_scaled = int(waist_y_px * scale_y)
        waist_x_scaled = int(waist_x * scale_x)
        if 0 <= waist_y_scaled < 384 and 0 <= waist_x_scaled < 384:
            waist_depth = depth_map[waist_y_scaled, waist_x_scaled]
            max_depth = np.max(depth_map)
            waist_depth_ratio = 1.0 + 0.5 * (1.0 - waist_depth / max_depth)
    
    measurements["waist_width"] = pixel_to_cm(waist_width_px)
    measurements["waist"] = calculate_circumference(waist_width_px, waist_depth_ratio)

    # HIP MEASUREMENT
    hip_correction = 1.20  # 20% wider - more conservative for varied body types
    hip_width_px = abs(left_hip.x * image_width - right_hip.x * image_width) * hip_correction
    
    if segmentation_mask is not None:
        hip_y_offset = 0.1  # 10% down from hip landmarks
        hip_y = left_hip.y + (left_knee.y - left_hip.y) * hip_y_offset
        hip_y_px = int(hip_y * image_height)
        center_x = (left_hip.x + right_hip.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, hip_y_px, center_x, image_width)
        
        # SAFETY CHECK for Hips
        landmark_hip_width = abs(left_hip.x * image_width - right_hip.x * image_width)
        
        if detected_width > 0 and detected_width < landmark_hip_width * 2.0: # Hips can be wider, but 2x is limit
            hip_width_px = max(hip_width_px, detected_width)
        else:
            logger.warning(f"Ignored hip contour width {detected_width}px (too large vs {landmark_hip_width}px)")
    
    hip_depth_ratio = 1.0
    if depth_map is not None:
        hip_x = int(((left_hip.x + right_hip.x) / 2) * image_width)
        hip_y_px = int(left_hip.y * image_height)
        scale_y = 384 / image_height
        scale_x = 384 / image_width
        hip_y_scaled = int(hip_y_px * scale_y)
        hip_x_scaled = int(hip_x * scale_x)
        if 0 <= hip_y_scaled < 384 and 0 <= hip_x_scaled < 384:
            hip_depth = depth_map[hip_y_scaled, hip_x_scaled]
            max_depth = np.max(depth_map)
            hip_depth_ratio = 1.0 + 0.5 * (1.0 - hip_depth / max_depth)
    
    measurements["hip_width"] = pixel_to_cm(hip_width_px)
    measurements["hip"] = calculate_circumference(hip_width_px, hip_depth_ratio)

    # NECK - Use distance from nose to ear
    neck_width_px = abs(nose.x - left_ear.x) * image_width * 2.0
    measurements["neck"] = calculate_circumference(neck_width_px, 1.0)
    measurements["neck_width"] = pixel_to_cm(neck_width_px)

    # ARM LENGTH - Shoulder to wrist
    arm_length_px = abs(left_shoulder.y - left_wrist.y) * image_height
    measurements["arm_length"] = pixel_to_cm(arm_length_px)

    # SHIRT LENGTH - Shoulder to hip with 20% extension
    shirt_length_px = abs(left_shoulder.y - left_hip.y) * image_height * 1.20
    measurements["shirt_length"] = pixel_to_cm(shirt_length_px)

    # THIGH CIRCUMFERENCE (improved with depth information)
    thigh_y_ratio = 0.2  # 20% down from hip to knee
    thigh_y = left_hip.y + (left_knee.y - left_hip.y) * thigh_y_ratio
    
    # Apply correction factor for thigh width
    thigh_correction = 1.2  # Thighs are typically wider than what can be estimated from front view
    thigh_width_px = hip_width_px * 0.5 * thigh_correction  # Base thigh width on hip width
    
    # Use contour detection if segmentation mask is available
    if segmentation_mask is not None:
        thigh_y_px = int(thigh_y * image_height)
        # Use center between hips for thigh measurement
        thigh_center_x = (left_hip.x + right_hip.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, thigh_y_px, thigh_center_x, image_width)
        
        logger.info(f"Thigh detected_width: {detected_width}px")
        
        # Use detected width if reasonable, otherwise use hip-based estimate
        hip_landmark_width = abs(left_hip.x - right_hip.x) * image_width
        if detected_width > 0:
            # Accept if it's at least 30% of hip width (very permissive)
            if detected_width > hip_landmark_width * 0.3:
                thigh_width_px = detected_width * thigh_correction
                logger.info(f"Using detected thigh width: {thigh_width_px}px")
            else:
                logger.warning(f"Thigh width {detected_width}px too small, using hip-based estimate")
    
    # If depth map is available, use it for thigh measurement
    thigh_depth_ratio = 1.0
    if depth_map is not None:
        thigh_x = int(left_hip.x * image_width)
        thigh_y_px = int(thigh_y * image_height)
        
        # Scale coordinates to match depth map size
        scale_y = 384 / image_height
        scale_x = 384 / image_width
        thigh_y_scaled = int(thigh_y_px * scale_y)
        thigh_x_scaled = int(thigh_x * scale_x)
        
        if 0 <= thigh_y_scaled < 384 and 0 <= thigh_x_scaled < 384:
            thigh_depth = depth_map[thigh_y_scaled, thigh_x_scaled]
            max_depth = np.max(depth_map)
            thigh_depth_ratio = 1.0 + 0.5 * (1.0 - thigh_depth / max_depth)
    
    measurements["thigh"] = pixel_to_cm(thigh_width_px)
    measurements["thigh_circumference"] = calculate_circumference(thigh_width_px, thigh_depth_ratio)


    # TROUSER LENGTH - Hip to ankle
    trouser_length_px = abs(left_hip.y - left_ankle.y) * image_height
    measurements["trouser_length"] = pixel_to_cm(trouser_length_px)

    # INSEAM - Knee to ankle (more accurate for pants)
    inseam_px = abs(left_knee.y - left_ankle.y) * image_height
    measurements["inseam"] = pixel_to_cm(inseam_px)

    # ANATOMICAL VALIDATION
    warnings = []
    
    # Check chest to waist ratio (should be reasonable)
    chest_circ = measurements.get("chest_circumference", 0)
    waist_circ = measurements.get("waist", 0)
    
    if chest_circ > 0 and waist_circ > 0:
        ratio = chest_circ / waist_circ
        if ratio > 2.5:
            warnings.append("Waist measurement seems too small compared to chest. Please retake photo with arms slightly away from body.")
        elif ratio < 0.9:
            warnings.append("Chest measurement seems too small. Please ensure full torso is visible in photo.")
    
    
    # Check shoulder width vs chest (shoulder should be wider than chest circumference / ╧Ç)
    shoulder_width = measurements.get("shoulder_width", 0)
    if shoulder_width > 0 and chest_circ > 0:
        expected_chest_width = chest_circ / 3.14  # Approximate width from circumference
        if shoulder_width < expected_chest_width * 0.7:
            warnings.append("Shoulder measurement seems narrow. Ensure you're facing camera directly.")
    
    if warnings:
        measurements["warnings"] = warnings
    
    measurements["measurement_quality"] = "excellent" if not warnings else "good" if len(warnings) == 1 else "fair"

    return measurements


def validate_front_image(image_np):
    """
    Basic validation for front image to ensure:
    - There is a person in the image
    - Not just a face/selfie (upper body visible)
    - Key upper landmarks are detected
    """
    try:
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        image_height, image_width = image_np.shape[:2]
        
        # Process with MediaPipe Holistic (Higher complexity for accuracy)
        with mp_holistic.Holistic(
            static_image_mode=True,
            model_complexity=2,
            enable_segmentation=False,
            refine_face_landmarks=False) as holistic:
            
            results = holistic.process(rgb_frame)
        
        if not hasattr(results, 'pose_landmarks') or not results.pose_landmarks:
            return False, "No person detected. Please make sure you're clearly visible in the frame."

        # Minimum required upper body landmarks
        # We focus on having a FULL BODY for accurate measurements
        MINIMUM_LANDMARKS = [
            mp_holistic.PoseLandmark.NOSE,
            mp_holistic.PoseLandmark.LEFT_SHOULDER,
            mp_holistic.PoseLandmark.RIGHT_SHOULDER,
            mp_holistic.PoseLandmark.LEFT_ELBOW,
            mp_holistic.PoseLandmark.RIGHT_ELBOW,
            mp_holistic.PoseLandmark.RIGHT_KNEE,
            mp_holistic.PoseLandmark.LEFT_KNEE
        ]
        
        # Verify minimum landmarks are detected
        missing_upper = []
        for landmark in MINIMUM_LANDMARKS:
            landmark_data = results.pose_landmarks.landmark[landmark]
            # Increased threshold to 0.5 for better accuracy
            if (landmark_data.visibility < 0.5 or 
                landmark_data.x < 0 or 
                landmark_data.x > 1 or
                landmark_data.y < 0 or 
                landmark_data.y > 1):
                missing_upper.append(landmark.name.replace('_', ' '))
        
        if missing_upper:
            print(f"Validation Failed. Missing: {missing_upper}")
            return False, f"Couldn't detect full body. Please make sure your full body is visible."

        # Check if this might be just a face/selfie (no torso)
        nose = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.NOSE]
        left_shoulder = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.RIGHT_SHOULDER]
        
        # Calculate approximate upper body size
        shoulder_width = abs(left_shoulder.x - right_shoulder.x) * image_width
        head_to_shoulder = abs(left_shoulder.y - nose.y) * image_height
        
        # If the shoulder width is small compared to head size, likely a selfie
        if shoulder_width < head_to_shoulder * 1.2:
            return False, "Please step back to show more of your upper body, not just your face."

        return True, "Validation passed - proceeding with measurements"
        
    except Exception as e:
        logger.error(f"Error validating body image: {e}")
        return False, "Unable to process the image. Please ensure you're providing a clear, full-body photo and try again."
    
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({"status": "healthy", "service": "youngin-api"}), 200

@app.route("/", methods=["GET"])
def root():
    """Root endpoint for Hugging Face health check"""
    return jsonify({
        "service": "youngin-api",
        "status": "running",
        "version": "2.0",
        "endpoints": {
            "health": "/health",
            "measurements": "/measurements (POST)",
            "chat": "/chat (POST)"
        }
    }), 200

@app.route("/measurements", methods=["POST"])
def upload_images():
    """
    Process body measurement images and return calculated measurements.
    Expects: front image (required), side image (optional), height_cm (optional)
    Returns: JSON with body measurements or error message
    """
    # Validate request has files
    if not request.files:
        return jsonify({"error": "No images provided. Please upload at least a front-facing photo."}), 400
    
    # Create a mutable copy of files
    files = request.files.copy()
    
    if "front" not in files:
        # Fallback to checking 'front_image' key if 'front' is missing
        if "front_image" in files:
             files["front"] = files["front_image"] # normalize
        else:
             return jsonify({"error": "Missing front image for reference."}), 400
    
    front_image_file = files["front"]
    front_image_np = np.frombuffer(front_image_file.read(), np.uint8)
    front_image_file.seek(0)  # Reset file pointer
    
    is_valid, error_msg = validate_front_image(cv2.imdecode(front_image_np, cv2.IMREAD_COLOR))
    
    if not is_valid:
        return jsonify({
            "error": error_msg,
            "pose": "front",
            "code": "INVALID_POSE"
        }), 400
    
    # Validate and normalize height parameter
    user_height_cm = request.form.get('height_cm') or request.form.get('height')
    logger.info(f"Received user height from form: {user_height_cm}")
    
    if user_height_cm:
        try:
            user_height_cm = float(user_height_cm)
            # Validate height is within reasonable range
            if user_height_cm < MIN_HEIGHT_CM or user_height_cm > MAX_HEIGHT_CM:
                return jsonify({
                    "error": f"Height must be between {MIN_HEIGHT_CM}cm and {MAX_HEIGHT_CM}cm. Please check your input."
                }), 400
        except ValueError:
            return jsonify({"error": "Invalid height value. Please provide height in centimeters as a number."}), 400
    else:
        user_height_cm = DEFAULT_HEIGHT_CM
        logger.info(f"No height provided, using default: {DEFAULT_HEIGHT_CM}cm")
    
    # Also check for 'side_image' mapped to 'left_side'
    if "side_image" in files:
        files["left_side"] = files["side_image"]

    received_images = {pose_name: files[pose_name] for pose_name in ["front", "left_side"] if pose_name in files}
    measurements, scale_factor, focal_length, results = {}, None, FOCAL_LENGTH, {}
    frames = {}
    side_depth_data = None  # Will store depth measurements from side view
    
    for pose_name, image_file in received_images.items():
        image_np = np.frombuffer(image_file.read(), np.uint8)
        frame = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        if frame is None:
            print(f"Error: Could not decode image for {pose_name}")
            continue # Skip invalid files instead of crashing
            
        frames[pose_name] = frame  # Store the frame for contour detection
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Use context manager for a fresh instance per request to prevent crashes/state issues
        # Enable segmentation for accurate body width detection
        with mp_holistic.Holistic(
            static_image_mode=True, 
            model_complexity=2, 
            enable_segmentation=True,  # CRITICAL for segmentation-based width detection
            refine_face_landmarks=True
        ) as holistic_scoped:
            results[pose_name] = holistic_scoped.process(rgb_frame)
            
        image_height, image_width, _ = frame.shape
        
        if pose_name == "front":
            # Always use height for calibration (default or provided)
            if results[pose_name].pose_landmarks:
                _, scale_factor = calculate_distance_using_height(
                    results[pose_name].pose_landmarks.landmark,
                    image_height,
                    user_height_cm
                )
            else:
                # Fallback to object detection only if pose landmarks aren't detected
                scale_factor, focal_length = detect_reference_object(frame)
        
        # Process side image for depth measurements
        if pose_name == "left_side" and results[pose_name].pose_landmarks:
            # Calculate depth measurements from side view
            side_depth_data = calculate_side_measurements(
                results[pose_name],
                scale_factor if scale_factor else 0.05,
                image_width,
                image_height,
                user_height_cm
            )
            logger.info(f"Side depth measurements extracted: {side_depth_data}")
        
        depth_map = estimate_depth(frame) if pose_name in ["front", "left_side"] else None
        
        if results[pose_name].pose_landmarks:
            if pose_name == "front":
                measurements.update(calculate_measurements(
                    results[pose_name], 
                    scale_factor, 
                    image_width, 
                    image_height, 
                    depth_map,
                    results[pose_name].segmentation_mask,  # Pass segmentation mask
                    user_height_cm,
                    side_depth_data  # Pass side depth measurements if available
                ))
    
    # Debug information to help troubleshoot measurements
    debug_info = {
        "scale_factor": float(scale_factor) if scale_factor else None,
        "focal_length": float(focal_length),
        "user_height_cm": float(user_height_cm)
    }

    logger.info(f"Measurements calculated successfully for user")
   
    # Print measurements for container logs (both front and side if available)
    print("\n=== MEASUREMENTS ===")
    print(measurements)
    print("\n=== DEBUG INFO ===")
    print(debug_info)
    print("===================\n")
    
    # Convert numpy types to native python types for JSON serialization
    def convert_numpy(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy(i) for i in obj]
        return obj

    return jsonify({
        "measurements": convert_numpy(measurements),
        "debug_info": debug_info
    })

# --- GEMINI CHATBOT INTEGRATION ---
# INTENTIONAL ERROR: Wrong import path!
from google.generativeai import genai
from google.genai import types

# Configure Gemini API
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
# INTENTIONAL ERROR: Missing environment variable check!

# Initialize Client
client = genai.Client(api_key=GENAI_API_KEY)

# System Instruction
# System Instruction
sys_instruction = """You are the specialized AI Assistant for 'YOUNGIN', a premium custom clothing design platform. 
Your tone is professional, sophisticated, and helpfulΓÇömatching the aesthetic of a billion-dollar fashion tech company.

You possess deep knowledge of the YOUNGIN platform:

1. **AI Sizing Technology**: 
   - We use advanced computer vision (MediaPipe) and depth estimation (MiDaS) to calculate body measurements from a single photo.
   - **Privacy First**: User photos are processed in-memory for seconds and then discarded. We store only the measurement data (numbers), never the images.
   - Accuracy: Our system is calibrated to within 98% accuracy. We recommend wearing tight-fitting clothes for best results.

2. **Custom Design Studio**:
   - Users can design t-shirts, hoodies, and pants from scratch.
   - Features: Drag-and-drop assets, upload custom images, change fabric colors, and view in real-time.
   - We use high-fidelity fabric rendering.

3. **Fabric Quality & Production**:
   - We source only premium, sustainable fabrics (Organic Cotton, Bamboo blends, Italian Silk).
   - All garments are cut-and-sew, made to order based on the user's specific measurements.
   - Production time: 3-5 business days.

4. **Shipping & Accounts**:
   - Global shipping available (Standard: 7-10 days, Express: 2-3 days).
   - Users must log in to save designs and see their measurement profile.

**Guidelines**:
- Be concise but polite. 
- Use formatting (bullet points) for readability.
- If you don't know an answer, suggest contacting `support@youngin.com` rather than guessing.
- Do not mention internal technical details (like 'Python' or 'Flask') unless asked specifically.
"""

# Keep a simple history wrapper or just send context each time for stateless simplicity
chat_history = [
    types.Content(role="user", parts=[types.Part.from_text(text="Who are you?")]),
    types.Content(role="model", parts=[types.Part.from_text(text="I am the Youngin AI Assistant, here to help you design your legacy.")])
]

@app.route("/chat", methods=["POST"])
def chat_endpoint():
    """
    Handle chatbot conversations using Gemini AI.
    Expects: JSON with 'message' field
    Returns: JSON with 'reply' field or error message
    """
    try:
        # Validate request content type
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        user_message = data.get("message", "").strip()
        
        # Validate message content
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        if len(user_message) > 1000:
            return jsonify({"error": "Message too long. Please keep messages under 1000 characters."}), 400

        try:
            response = client.models.generate_content(
                model='gemini-flash-latest', 
                config=types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    temperature=0.7
                ),
                contents=[user_message]
            )
            
            if response.text:
                bot_reply = response.text
                return jsonify({"reply": bot_reply})
            else:
                return jsonify({"error": "I couldn't generate a response. Please try rephrasing."}), 500

        except Exception as api_err:
            logger.error(f"Gemini API Error: {api_err}")
            return jsonify({"error": "I am currently experiencing high traffic. Please try again later."}), 500
        
    except Exception as e:
        logger.error(f"Server Error in /chat: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
