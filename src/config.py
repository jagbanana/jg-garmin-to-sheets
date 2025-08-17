from dataclasses import dataclass, fields
from datetime import date
from typing import Optional

# 1. The Dataclass defines the data structure
@dataclass
class GarminMetrics:
    date: date
    sleep_score: Optional[float] = None
    sleep_length: Optional[float] = None
    weight: Optional[float] = None
    body_fat: Optional[float] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    active_calories: Optional[int] = None
    resting_calories: Optional[int] = None
    resting_heart_rate: Optional[int] = None
    average_stress: Optional[int] = None
    training_status: Optional[str] = None
    vo2max_running: Optional[float] = None
    vo2max_cycling: Optional[float] = None
    intensity_minutes: Optional[int] = None
    all_activity_count: Optional[int] = None
    running_activity_count: Optional[int] = None
    running_distance: Optional[float] = None
    cycling_activity_count: Optional[int] = None
    cycling_distance: Optional[float] = None
    strength_activity_count: Optional[int] = None
    strength_duration: Optional[float] = None
    cardio_activity_count: Optional[int] = None
    cardio_duration: Optional[float] = None
    tennis_activity_count: Optional[int] = None
    tennis_activity_duration: Optional[float] = None
    overnight_hrv: Optional[int] = None
    hrv_status: Optional[str] = None
    steps: Optional[int] = None
    activity_calories: Optional[int] = None
    # TODO: To add a new attribute, just add it here!

# 2. The Headers list defines the output order and names
HEADERS = [
    "Date", "Sleep Score", "Sleep Length", "HRV (ms)", "HRV Status", "Weight (kg)", "Body Fat %",
    "Blood Pressure Systolic", "Blood Pressure Diastolic", "Active Calories",
    "Resting Calories", "Resting Heart Rate", "Average Stress", "Training Status",
    "VO2 Max Running", "VO2 Max Cycling", "Intensity Minutes", "All Activity Count",
    "Running Activity Count", "Running Distance (km)", "Cycling Activity Count",
    "Cycling Distance (km)", "Strength Activity Count", "Strength Duration",
    "Cardio Activity Count", "Cardio Duration",
    "Tennis Activity Count", "Tennis Activity Duration", "Steps", "Activity Calories"
]

# 3. The Map connects the Headers to the Dataclass attributes
HEADER_TO_ATTRIBUTE_MAP = {
    "Date": "date",
    "Sleep Score": "sleep_score",
    "Sleep Length": "sleep_length",
    "Weight (kg)": "weight", # Note: Changed from weight_kg for simplicity
    "Body Fat %": "body_fat",
    "Blood Pressure Systolic": "blood_pressure_systolic",
    "Blood Pressure Diastolic": "blood_pressure_diastolic",
    "Active Calories": "active_calories",
    "Resting Calories": "resting_calories",
    "Resting Heart Rate": "resting_heart_rate",
    "Average Stress": "average_stress",
    "Training Status": "training_status",
    "VO2 Max Running": "vo2max_running",
    "VO2 Max Cycling": "vo2max_cycling",
    "Intensity Minutes": "intensity_minutes",
    "All Activity Count": "all_activity_count",
    "Running Activity Count": "running_activity_count",
    "Running Distance (km)": "running_distance",
    "Cycling Distance (km)": "cycling_distance",
    "Strength Activity Count": "strength_activity_count",
    "Strength Duration": "strength_duration",
    "Cardio Activity Count": "cardio_activity_count",
    "Cardio Duration": "cardio_duration",
    "HRV (ms)": "overnight_hrv",
    "HRV Status": "hrv_status",
    "Tennis Activity Count": "tennis_activity_count",
    "Tennis Activity Duration": "tennis_activity_duration",
    "Steps" : "steps",
    "Activity Calories" : "activity_calories"
}

## Helper to get all attribute names from the dataclass
#ALL_METRIC_ATTRIBUTES = [field.name for field in fields(GarminMetrics)]
