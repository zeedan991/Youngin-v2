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

# Configure CORS - but CORS not imported!
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
# This will cause an error - CORS is not defined
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

logger.info("📦 Initializing MediaPipe models...")
mp_pose = mp.solutions.pose
mp_holistic = mp.solutions.holistic
pose = mp_pose.Pose(model_complexity=2)
holistic = mp_holistic.Holistic()
logger.info("✅ MediaPipe models initialized")

# Constants for measurement calculations
KNOWN_OBJECT_WIDTH_CM = 21.0
FOCAL_LENGTH = 600
DEFAULT_HEIGHT_CM = 152.0
MIN_HEIGHT_CM = 100.0
MAX_HEIGHT_CM = 250.0

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
    nose_y = landmarks[mp_pose.PoseLandmark.NOSE.value].y * image_height
    
    bottom_foot = max(
        landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y,
        landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y
    ) * image_height
    
    nose_to_ankle_px = abs(bottom_foot - nose_y)
    person_height_px = nose_to_ankle_px / 0.88
    
    distance = (user_height_cm * FOCAL_LENGTH) / person_height_px
    scale_factor = user_height_cm / person_height_px
    
    logger.info(f"Height calculation: nose_to_ankle={nose_to_ankle_px}px, estimated_full_height={person_height_px}px, scale_factor={scale_factor}")
    
    return distance, scale_factor

def get_width_from_segmentation(segmentation_mask, height_px, center_x, image_width):
    """
    Scan horizontally at a specific height using MediaPipe segmentation mask.
    """
    if segmentation_mask is None:
        return 0
    
    mask_height, mask_width = segmentation_mask.shape
    if height_px >= mask_height:
        height_px = mask_height - 1
    
    center_x_px = int(center_x * mask_width)
    horizontal_line = segmentation_mask[height_px, :]
    
    left_edge, right_edge = center_x_px, center_x_px
    
    for i in range(center_x_px, 0, -1):
        if horizontal_line[i] < 0.1:
            left_edge = i
            break
    
    for i in range(center_x_px, mask_width):
        if horizontal_line[i] < 0.1:
            right_edge = i
            break
            
    width_px = right_edge - left_edge
    width_px = int(width_px * (image_width / mask_width))
    
    min_width = 0.05 * image_width
    if width_px < min_width:
        return 0
        
    return width_px

def calculate_side_measurements(results, scale_factor, image_width, image_height, user_height_cm=None):
    """Extract depth measurements from side view."""
    landmarks = results.pose_landmarks.landmark
    
    if user_height_cm:
        _, scale_factor = calculate_distance_using_height(landmarks, image_height, user_height_cm)
    
    def pixel_to_cm(value):
        return round(value * scale_factor, 2)
    
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    
    front_x = max(left_shoulder.x, right_shoulder.x, nose.x)
    back_x = min(left_shoulder.x, right_shoulder.x)
    
    chest_depth_px = abs(front_x - back_x) * image_width
    chest_depth_cm = pixel_to_cm(chest_depth_px) * 1.2
    
    waist_depth_cm = chest_depth_cm * 0.85
    
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

    if user_height_cm:
        _, scale_factor = calculate_distance_using_height(landmarks, image_height, user_height_cm)

    def pixel_to_cm(value):
        return round(value * scale_factor, 2)
    
    def calculate_circumference(width_px, depth_ratio=1.0):
        width_cm = width_px * scale_factor
        estimated_depth_cm = width_cm * depth_ratio * 0.7
        half_width = width_cm / 2
        half_depth = estimated_depth_cm / 2
        return round(2 * np.pi * np.sqrt((half_width**2 + half_depth**2) / 2), 2)

    measurements = {}

    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
    left_knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value]
    left_ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
    nose = landmarks[mp_pose.PoseLandmark.NOSE.value]
    left_ear = landmarks[mp_pose.PoseLandmark.LEFT_EAR.value]

    shoulder_width_px = abs(left_shoulder.x - right_shoulder.x) * image_width
    shoulder_correction = 1.1
    shoulder_width_px *= shoulder_correction
    
    measurements["shoulder_width"] = pixel_to_cm(shoulder_width_px)

    chest_y_ratio = 0.15
    chest_y = left_shoulder.y + (left_hip.y - left_shoulder.y) * chest_y_ratio
    
    chest_correction = 1.08
    chest_width_px = abs((right_shoulder.x - left_shoulder.x) * image_width) * chest_correction
    
    if segmentation_mask is not None:
        chest_y_px = int(chest_y * image_height)
        center_x = (left_shoulder.x + right_shoulder.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, chest_y_px, center_x, image_width)
        if detected_width > 0:
            landmark_width = abs(right_shoulder.x - left_shoulder.x) * image_width
            if detected_width < landmark_width * 1.5:
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

    waist_y_ratio = 0.35
    waist_y = left_shoulder.y + (left_hip.y - left_shoulder.y) * waist_y_ratio
    
    if segmentation_mask is not None:
        waist_y_px = int(waist_y * image_height)
        center_x = (left_hip.x + right_hip.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, waist_y_px, center_x, image_width)
        
        hip_landmark_width = abs(right_hip.x - left_hip.x) * image_width
        
        if detected_width > 0 and detected_width < hip_landmark_width * 1.5:
             waist_width_px = detected_width
        else:
             logger.warning(f"Ignored waist contour width {detected_width}px (unreasonable)")
             waist_width_px = hip_landmark_width * 0.9
    else:
        waist_width_px = abs(right_hip.x - left_hip.x) * image_width * 0.9
    
    waist_correction = 1.05
    waist_width_px *= waist_correction
    
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

    hip_correction = 1.20
    hip_width_px = abs(left_hip.x * image_width - right_hip.x * image_width) * hip_correction
    
    if segmentation_mask is not None:
        hip_y_offset = 0.1
        hip_y = left_hip.y + (left_knee.y - left_hip.y) * hip_y_offset
        hip_y_px = int(hip_y * image_height)
        center_x = (left_hip.x + right_hip.x) / 2
        detected_width = get_width_from_segmentation(segmentation_mask, hip_y_px, center_x, image_width)
        
        landmark_hip_width = abs(left_hip.x * image_width - right_hip.x * image_width)
        
        if detected_width > 0 and detected_width < landmark_hip_width * 2.0:
            hip_width_px = max(hip_width_px, detected_width)
        else:
            logger.warning(f"Ignored hip contour width {detected_width}px (too large vs {landmark_hip_width}px)")
    
    measurements["hip_width"] = pixel_to_cm(hip_width_px)
    measurements["hip"] = calculate_circumference(hip_width_px, 1.0)

    neck_width_px = abs(nose.x - left_ear.x) * image_width * 2.0
    measurements["neck"] = calculate_circumference(neck_width_px, 1.0)
    measurements["neck_width"] = pixel_to_cm(neck_width_px)

    arm_length_px = abs(left_shoulder.y - left_wrist.y) * image_height
    measurements["arm_length"] = pixel_to_cm(arm_length_px)

    shirt_length_px = abs(left_shoulder.y - left_hip.y) * image_height * 1.20
    measurements["shirt_length"] = pixel_to_cm(shirt_length_px)

    trouser_length_px = abs(left_hip.y - left_ankle.y) * image_height
    measurements["trouser_length"] = pixel_to_cm(trouser_length_px)

    return measurements


def validat_front_image(image_np):
    """Basic validation for front image - TYPO IN FUNCTION NAME!"""
    try:
        rgb_frame = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
        image_height, image_width = image_np.shape[:2]
        
        with mp_holistic.Holistic(
            static_image_mode=True,
            model_complexity=2,
            enable_segmentation=False,
            refine_face_landmarks=False) as holistic:
            
            results = holistic.process(rgb_frame)
        
        if not hasattr(results, 'pose_landmarks') or not results.pose_landmarks:
            return False, "No person detected. Please make sure you're clearly visible in the frame."

        MINIMUM_LANDMARKS = [
            mp_holistic.PoseLandmark.NOSE,
            mp_holistic.PoseLandmark.LEFT_SHOULDER,
            mp_holistic.PoseLandmark.RIGHT_SHOULDER,
            mp_holistic.PoseLandmark.LEFT_ELBOW,
            mp_holistic.PoseLandmark.RIGHT_ELBOW,
            mp_holistic.PoseLandmark.RIGHT_KNEE,
            mp_holistic.PoseLandmark.LEFT_KNEE
        ]
        
        missing_upper = []
        for landmark in MINIMUM_LANDMARKS:
            landmark_data = results.pose_landmarks.landmark[landmark]
            if (landmark_data.visibility < 0.5 or
                landmark_data.x < 0 or 
                landmark_data.x > 1 or
                landmark_data.y < 0 or 
                landmark_data.y > 1):
                missing_upper.append(landmark.name.replace('_', ' '))
        
        if missing_upper:
            return False, f"Couldn't detect full body. Please make sure your full body is visible."

        nose = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.NOSE]
        left_shoulder = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = results.pose_landmarks.landmark[mp_holistic.PoseLandmark.RIGHT_SHOULDER]
        
        shoulder_width = abs(left_shoulder.x - right_shoulder.x) * image_width
        head_to_shoulder = abs(left_shoulder.y - nose.y) * image_height
        
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
            "measurements": "/measurements (POST)"
        }
    }), 200

@app.route("/measurements", methods=["POST"])
def upload_images():
    if "front" not in request.files:
        return jsonify({"error": "Missing front image for reference."}), 400
    
    front_image_file = request.files["front"]
    front_image_np = np.frombuffer(front_image_file.read(), np.uint8)
    front_image_file.seek(0)
    
    is_valid, error_msg = validat_front_image(cv2.imdecode(front_image_np, cv2.IMREAD_COLOR))
    
    if not is_valid:
        return jsonify({
            "error": error_msg,
            "pose": "front",
            "code": "INVALID_POSE"
        }), 400
    
    user_height_cm = request.form.get('height_cm')
    if user_height_cm:
        try:
            user_height_cm = float(user_height_cm)
        except ValueError:
            user_height_cm = DEFAULT_HEIGHT_CM
    else:
        user_height_cm = DEFAULT_HEIGHT_CM
    
    received_images = {pose_name: request.files[pose_name] for pose_name in ["front", "left_side"] if pose_name in request.files}
    measurements, scale_factor, focal_length, results = {}, None, FOCAL_LENGTH, {}
    frames = {}
    
    for pose_name, image_file in received_images.items():
        image_np = np.frombuffer(image_file.read(), np.uint8)
        frame = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        frames[pose_name] = frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results[pose_name] = holistic.process(rgb_frame)
        image_height, image_width, _ = frame.shape
        
        if pose_name == "front":
            if results[pose_name].pose_landmarks:
                _, scale_factor = calculate_distance_using_height(
                    results[pose_name].pose_landmarks.landmark,
                    image_height,
                    user_height_cm
                )
            else:
                scale_factor, focal_length = detect_reference_object(frame)
        
        depth_map = estimate_depth(frame) if pose_name in ["front", "left_side"] else None
        
        if results[pose_name].pose_landmarks:
            if pose_name == "front":
                measurements.update(calculate_measurements(
                    results[pose_name], 
                    scale_factor, 
                    image_width, 
                    image_height, 
                    depth_map,
                    results[pose_name].segmentation_mask,
                    user_height_cm
                ))
    
    debug_info = {
        "scale_factor": float(scale_factor) if scale_factor else None,
        "focal_length": float(focal_length),
        "user_height_cm": float(user_height_cm)
    }

    print(measurements)
    
    return jsonify({ 
        "measurements": measurements,
        "debug_info": debug_info
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)