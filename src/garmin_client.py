from dataclasses import dataclass
from datetime import date
from typing import Dict, Any, Optional
import asyncio
import logging
import garminconnect

logger = logging.getLogger(__name__)

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

class GarminClient:
    def __init__(self, email: str, password: str):
        self.client = garminconnect.Garmin(email, password)
        self._authenticated = False

    async def authenticate(self):
        """Modified to handle non-async login method"""
        try:
            def login_wrapper():
                return self.client.login()
            
            await asyncio.get_event_loop().run_in_executor(None, login_wrapper)
            self._authenticated = True
        except garminconnect.GarminConnectAuthenticationError as e:
            raise Exception(f"Authentication failed: {str(e)}")

    async def _fetch_hrv_data(self, target_date_iso: str) -> Optional[Dict[str, Any]]:
        """Fetches HRV data for the given date."""
        # logger.info(f"Attempting to fetch HRV data for {target_date_iso}")
        try:
            hrv_data = await asyncio.get_event_loop().run_in_executor(
                None, self.client.get_hrv_data, target_date_iso
            )
            logger.debug(f"Raw HRV data for {target_date_iso}: {hrv_data}")
            return hrv_data
        except Exception as e:
            logger.error(f"Error fetching HRV data for {target_date_iso}: {str(e)}")
            return None

    async def get_metrics(self, target_date: date) -> GarminMetrics:
        if not self._authenticated:
            await self.authenticate()

        try:
            async def get_stats():
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.client.get_stats_and_body, target_date.isoformat()
                )

            async def get_sleep():
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.client.get_sleep_data, target_date.isoformat()
                )

            async def get_activities():
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.client.get_activities_by_date, 
                    target_date.isoformat(), target_date.isoformat()
                )

            async def get_user_summary():
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.client.get_user_summary, target_date.isoformat()
                )

            async def get_training_status():
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.client.get_training_status, target_date.isoformat()
                )
            
            async def get_hrv():
                return await self._fetch_hrv_data(target_date.isoformat())

            # Fetch data concurrently
            stats, sleep_data, activities, summary, training_status, hrv_payload = await asyncio.gather(
                get_stats(), get_sleep(), get_activities(), get_user_summary(), get_training_status(), get_hrv()
            )

            # Debug logging
            logger.debug(f"Raw stats data: {stats}")
            logger.debug(f"Raw sleep data: {sleep_data}")
            logger.debug(f"Raw activities data: {activities}")
            logger.debug(f"Raw summary data: {summary}")
            logger.debug(f"Raw training status data: {training_status}")
            logger.debug(f"Raw HRV payload: {hrv_payload}")

            # Process HRV data
            overnight_hrv_value: Optional[int] = None
            hrv_status_value: Optional[str] = None
            # Process HRV data
            if hrv_payload: # <--- Key check for hrv_payload itself
                hrv_summary = hrv_payload.get('hrvSummary') # Get hrvSummary first
                if hrv_summary: # <--- Key check for hrv_summary
                    # Safely extract hrv_value (lastNightAvg)
                    overnight_hrv_value = hrv_summary.get('lastNightAvg')

                    # Safely extract hrv_status
                    hrv_status_value = hrv_summary.get('status')
                    # logger.info(f"Extracted HRV: {overnight_hrv_value}, Status: {hrv_status_value} for {target_date}")
                else:
                    logger.warning(f"hrvSummary not found in hrv_payload for {target_date}. HRV metrics will be blank.")
            else:
                logger.warning(f"hrv_payload for {target_date} is None. HRV metrics will be blank.")


            # Process activities
            running_count = 0
            running_distance = 0
            cycling_count = 0
            cycling_distance = 0
            strength_count = 0
            strength_duration = 0
            cardio_count = 0
            cardio_duration = 0
            tennis_count = 0
            tennis_duration = 0

            if activities:
                for activity in activities:
                    activity_type = activity.get('activityType', {})
                    type_key = activity_type.get('typeKey', '').lower()
                    parent_type_id = activity_type.get('parentTypeId')

                    if 'run' in type_key or parent_type_id == 1:  # 1 is running
                        running_count += 1
                        running_distance += activity.get('distance', 0) / 1000  # Convert to km
                    elif 'virtual_ride' in type_key or 'cycling' in type_key or parent_type_id == 2:  # 2 is cycling
                        cycling_count += 1
                        cycling_distance += activity.get('distance', 0) / 1000
                    elif 'strength' in type_key:
                        strength_count += 1
                        strength_duration += activity.get('duration', 0) / 60  # Convert seconds to minutes
                    elif 'cardio' in type_key:
                        cardio_count += 1
                        cardio_duration += activity.get('duration', 0) / 60
                    elif 'tennis' in type_key: # Added for Tennis
                        tennis_count += 1
                        tennis_duration += activity.get('duration', 0) / 60 # Convert seconds to minutes
            else:
                logger.warning(f"Activities data for {target_date} is None. Activity metrics will be blank.")

            # Initialize metrics to None, as per GarminMetrics dataclass defaults
            sleep_score: Optional[float] = None
            sleep_length: Optional[float] = None
            weight: Optional[float] = None
            body_fat: Optional[float] = None
            blood_pressure_systolic: Optional[int] = None
            blood_pressure_diastolic: Optional[int] = None
            active_calories: Optional[int] = None
            resting_calories: Optional[int] = None
            intensity_minutes: Optional[int] = None
            resting_heart_rate: Optional[int] = None
            average_stress: Optional[int] = None
            vo2max_running: Optional[float] = None
            vo2max_cycling: Optional[float] = None
            training_status_phrase: Optional[str] = None

            # Process sleep data
            if sleep_data:
                sleep_dto = sleep_data.get('dailySleepDTO', {})
                if sleep_dto:
                    sleep_score = sleep_dto.get('sleepScores', {}).get('overall', {}).get('value')
                    sleep_time_seconds = sleep_dto.get('sleepTimeSeconds')
                    if sleep_time_seconds is not None and sleep_time_seconds > 0:
                        sleep_length = sleep_time_seconds / 3600  # Convert to hours
                else:
                    logger.warning(f"Daily sleep DTO not found in sleep data for {target_date}.")
            else:
                logger.warning(f"Sleep data for {target_date} is None. Sleep metrics will be blank.")

            # Get weight and body fat
            if stats:
                weight = stats.get('weight', 0) / 1000 if stats.get('weight') else None  # Convert grams to kg
                body_fat = stats.get('bodyFat')
            else:
                logger.warning(f"Stats data for {target_date} is None. Weight and body fat metrics will be blank.")

            # Get blood pressure (if available)
            if stats: # Already checked above, but for clarity
                blood_pressure_systolic = stats.get('systolic')
                blood_pressure_diastolic = stats.get('diastolic')
            # No else needed, as they are initialized to None

            # Get summary metrics
            if summary:
                active_calories = summary.get('activeKilocalories')
                resting_calories = summary.get('bmrKilocalories')
                intensity_minutes = (summary.get('moderateIntensityMinutes', 0) or 0) + (2 * (summary.get('vigorousIntensityMinutes', 0) or 0))
                resting_heart_rate = summary.get('restingHeartRate')
                average_stress = summary.get('averageStressLevel')
            else:
                logger.warning(f"User summary data for {target_date} is None. Summary metrics will be blank.")

            # Get VO2 max values and training status
            if training_status:
                vo2max_running = None
                vo2max_cycling = None
                most_recent_vo2max = training_status.get('mostRecentVO2Max')
                if most_recent_vo2max:
                    generic_vo2max = most_recent_vo2max.get('generic')
                    if generic_vo2max:
                        vo2max_running = generic_vo2max.get('vo2MaxValue')
                    
                    cycling_vo2max = most_recent_vo2max.get('cycling')
                    if cycling_vo2max:
                        vo2max_cycling = cycling_vo2max.get('vo2MaxValue')

                training_status_data = {} # Initialize to empty dict
                most_recent_training_status = training_status.get('mostRecentTrainingStatus')
                if most_recent_training_status:
                    latest_training_status_data = most_recent_training_status.get('latestTrainingStatusData')
                    if latest_training_status_data:
                        training_status_data = latest_training_status_data
                first_device = None
                if training_status_data:
                    # Get the first value from the dictionary, if any
                    for value in training_status_data.values():
                        first_device = value
                        break # Take the first one and exit
                
                if first_device: # Check if first_device is not None
                    training_status_phrase = first_device.get('trainingStatusFeedbackPhrase')
                else:
                    training_status_phrase = None # Ensure it's None if no device data or first_device is None
            else:
                logger.warning(f"Training status data for {target_date} is None. VO2 Max and training status metrics will be blank.")

            return GarminMetrics(
                date=target_date,
                sleep_score=sleep_score,
                sleep_length=sleep_length,
                weight=weight,
                body_fat=body_fat,
                blood_pressure_systolic=blood_pressure_systolic,
                blood_pressure_diastolic=blood_pressure_diastolic,
                active_calories=active_calories,
                resting_calories=resting_calories,
                resting_heart_rate=resting_heart_rate,
                average_stress=average_stress,
                training_status=training_status_phrase,
                vo2max_running=vo2max_running,
                vo2max_cycling=vo2max_cycling,
                intensity_minutes=intensity_minutes,
                all_activity_count=len(activities) if activities is not None else 0,
                running_activity_count=running_count,
                running_distance=running_distance,
                cycling_activity_count=cycling_count,
                cycling_distance=cycling_distance,
                strength_activity_count=strength_count,
                strength_duration=strength_duration,
                cardio_activity_count=cardio_count,
                cardio_duration=cardio_duration,
                tennis_activity_count=tennis_count, # Added for Tennis
                tennis_activity_duration=tennis_duration, # Added for Tennis
                overnight_hrv=overnight_hrv_value,
                hrv_status=hrv_status_value
            )

        except Exception as e:
            logger.error(f"Error fetching metrics for {target_date}: {str(e)}")
            # Return metrics object with just the date and potentially HRV if fetched before error
            return GarminMetrics(
                date=target_date,
                overnight_hrv=locals().get('overnight_hrv_value'), # Use locals() to get value if available
                hrv_status=locals().get('hrv_status_value')
            )