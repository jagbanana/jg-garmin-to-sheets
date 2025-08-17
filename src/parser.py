import logging
from datetime import date
from typing import Dict, Any, Tuple
from .config import GarminMetrics

# Suppress the noisy, non-error traceback from the http2 library
logging.getLogger("hpack").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def parse_garmin_data(
    target_date: date,
    stats: Dict[str, Any],
    sleep_data: Dict[str, Any],
    activities: list,
    summary: Dict[str, Any],
    training_status: Dict[str, Any],
    hrv_payload: Dict[str, Any]
) -> GarminMetrics:
    """
    Parses raw data from Garmin API calls and returns a clean GarminMetrics object.
    """
    try:
        # --- Process Activities ---
        (
            running_count, running_distance, cycling_count, cycling_distance,
            strength_count, strength_duration, cardio_count, cardio_duration,
            tennis_count, tennis_duration
        ) = _parse_activities(activities)

        # --- Process Sleep ---
        sleep_score, sleep_length = _parse_sleep(sleep_data, target_date)

        # --- Process HRV ---
        overnight_hrv, hrv_status = _parse_hrv(hrv_payload, target_date)

        # --- Process Training Status & VO2 Max ---
        training_status_phrase, vo2max_running, vo2max_cycling = _parse_training_status(training_status, target_date)

        # --- Process Stats (Weight, Body Fat, BP) ---
        weight, body_fat, bp_systolic, bp_diastolic = _parse_stats(stats, target_date)

        # --- Process Daily Summary (Calories, Steps, etc.) ---
        active_cals, resting_cals, steps, intensity_mins, rhr, avg_stress = _parse_summary(summary, target_date)

        return GarminMetrics(
            date=target_date.isoformat(), # Convert date to string here
            sleep_score=sleep_score,
            sleep_length=sleep_length,
            weight=weight,
            body_fat=body_fat,
            blood_pressure_systolic=bp_systolic,
            blood_pressure_diastolic=bp_diastolic,
            active_calories=active_cals,
            resting_calories=resting_cals,
            resting_heart_rate=rhr,
            average_stress=avg_stress,
            training_status=training_status_phrase,
            vo2max_running=vo2max_running,
            vo2max_cycling=vo2max_cycling,
            intensity_minutes=intensity_mins,
            all_activity_count=len(activities) if activities else 0,
            running_activity_count=running_count,
            running_distance=running_distance,
            cycling_activity_count=cycling_count,
            cycling_distance=cycling_distance,
            strength_activity_count=strength_count,
            strength_duration=strength_duration,
            cardio_activity_count=cardio_count,
            cardio_duration=cardio_duration,
            tennis_activity_count=tennis_count,
            tennis_activity_duration=tennis_duration,
            overnight_hrv=overnight_hrv,
            hrv_status=hrv_status,
            steps=steps
        )
    except Exception as e:
        logger.error(f"Error parsing metrics for {target_date}: {e}", exc_info=True)
        return GarminMetrics(date=target_date.isoformat()) # Also convert here for safety

def _parse_activities(activities: list) -> Tuple:
    """Helper to parse the activities list."""
    if not activities:
        return 0, 0.0, 0, 0.0, 0, 0.0, 0, 0.0, 0, 0.0

    running_count, running_distance = 0, 0.0
    cycling_count, cycling_distance = 0, 0.0
    strength_count, strength_duration = 0, 0.0
    cardio_count, cardio_duration = 0, 0.0
    tennis_count, tennis_duration = 0, 0.0

    for activity in activities:
        activity_type = activity.get('activityType', {})
        type_key = activity_type.get('typeKey', '').lower()

        if 'run' in type_key:
            running_count += 1
            running_distance += activity.get('distance', 0) / 1000.0
        elif 'cycling' in type_key or 'virtual_ride' in type_key:
            cycling_count += 1
            cycling_distance += activity.get('distance', 0) / 1000.0
        elif 'strength' in type_key:
            strength_count += 1
            strength_duration += activity.get('duration', 0) / 60.0
        elif 'cardio' in type_key:
            cardio_count += 1
            cardio_duration += activity.get('duration', 0) / 60.0
        elif 'tennis' in type_key:
            tennis_count += 1
            tennis_duration += activity.get('duration', 0) / 60.0
    
    return (running_count, running_distance, cycling_count, cycling_distance,
            strength_count, strength_duration, cardio_count, cardio_duration,
            tennis_count, tennis_duration)

def _parse_sleep(sleep_data: Dict[str, Any], target_date: date) -> Tuple:
    """Helper to parse sleep data safely."""
    if not sleep_data:
        logger.warning(f"Sleep data for {target_date} is None.")
        return None, None
    
    sleep_dto = sleep_data.get('dailySleepDTO')
    if not sleep_dto:
        logger.warning(f"Daily sleep DTO not found for {target_date}.")
        return None, None
        
    sleep_scores = sleep_dto.get('sleepScores')
    score = sleep_scores.get('overall', {}).get('value') if sleep_scores else None
    
    seconds = sleep_dto.get('sleepTimeSeconds')
    length = seconds / 3600.0 if seconds else None
    return score, length

def _parse_hrv(hrv_payload: Dict[str, Any], target_date: date) -> Tuple:
    """Helper to parse HRV data safely."""
    if not hrv_payload:
        logger.warning(f"HRV payload for {target_date} is None.")
        return None, None
        
    hrv_summary = hrv_payload.get('hrvSummary')
    if not hrv_summary:
        logger.warning(f"hrvSummary not found for {target_date}.")
        return None, None
        
    return hrv_summary.get('lastNightAvg'), hrv_summary.get('status')

def _parse_training_status(training_status: Dict[str, Any], target_date: date) -> Tuple:
    """Helper to parse training status and VO2 Max safely."""
    if not training_status:
        logger.warning(f"Training status data for {target_date} is None.")
        return None, None, None

    vo2_max_running, vo2_max_cycling = None, None
    most_recent_vo2max = training_status.get('mostRecentVO2Max')
    if most_recent_vo2max:
        generic_vo2max = most_recent_vo2max.get('generic')
        if generic_vo2max:
            vo2_max_running = generic_vo2max.get('vo2MaxValue')

        cycling_vo2max = most_recent_vo2max.get('cycling')
        if cycling_vo2max:
            vo2_max_cycling = cycling_vo2max.get('vo2MaxValue')

    most_recent_status = training_status.get('mostRecentTrainingStatus')
    status_phrase = most_recent_status.get('trainingStatusFeedbackPhrase') if most_recent_status else None
    
    return status_phrase, vo2_max_running, vo2_max_cycling

def _parse_stats(stats: Dict[str, Any], target_date: date) -> Tuple:
    """Helper to parse weight, body fat, and blood pressure."""
    if not stats:
        logger.warning(f"Stats data for {target_date} is None.")
        return None, None, None, None
    
    weight = stats.get('weight') / 1000.0 if stats.get('weight') else None
    body_fat = stats.get('bodyFat')
    bp_systolic = stats.get('systolic')
    bp_diastolic = stats.get('diastolic')
    return weight, body_fat, bp_systolic, bp_diastolic

def _parse_summary(summary: Dict[str, Any], target_date: date) -> Tuple:
    """Helper to parse daily summary stats like calories and steps."""
    if not summary:
        logger.warning(f"User summary data for {target_date} is None.")
        return None, None, None, None, None, None
    
    active_cals = summary.get('activeKilocalories')
    resting_cals = summary.get('bmrKilocalories')
    steps = summary.get('totalSteps')
    intensity_mins = (summary.get('moderateIntensityMinutes', 0) or 0) + (2 * (summary.get('vigorousIntensityMinutes', 0) or 0))
    rhr = summary.get('restingHeartRate')
    avg_stress = summary.get('averageStressLevel')
    return active_cals, resting_cals, steps, intensity_mins, rhr, avg_stress
