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

            # Fetch data concurrently
            stats, sleep_data, activities, summary, training_status = await asyncio.gather(
                get_stats(), get_sleep(), get_activities(), get_user_summary(), get_training_status()
            )

            # Debug logging
            logger.debug(f"Raw stats data: {stats}")
            logger.debug(f"Raw sleep data: {sleep_data}")
            logger.debug(f"Raw activities data: {activities}")
            logger.debug(f"Raw summary data: {summary}")
            logger.debug(f"Raw training status data: {training_status}")

            # Process activities
            running_count = 0
            running_distance = 0
            cycling_count = 0
            cycling_distance = 0
            strength_count = 0
            strength_duration = 0
            cardio_count = 0
            cardio_duration = 0

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

            # Process sleep data
            sleep_dto = sleep_data.get('dailySleepDTO', {})
            sleep_score = sleep_dto.get('sleepScores', {}).get('overall', {}).get('value')
            sleep_length = sleep_dto.get('sleepTimeSeconds', 0) / 3600  # Convert to hours

            # Get weight and body fat
            weight = stats.get('weight', 0) / 1000 if stats.get('weight') else None  # Convert grams to kg
            body_fat = stats.get('bodyFat')

            # Get blood pressure (if available)
            blood_pressure_systolic = stats.get('systolic')
            blood_pressure_diastolic = stats.get('diastolic')

            # Get summary metrics
            active_calories = summary.get('activeKilocalories')
            resting_calories = summary.get('bmrKilocalories')
            intensity_minutes = (summary.get('moderateIntensityMinutes', 0) or 0) + (summary.get('vigorousIntensityMinutes', 0) or 0)
            resting_heart_rate = summary.get('restingHeartRate')
            average_stress = summary.get('averageStressLevel')

            # Get VO2 max values
            vo2max_running = training_status.get('mostRecentVO2Max', {}).get('generic', {}).get('vo2MaxValue')
            vo2max_cycling = training_status.get('mostRecentVO2Max', {}).get('cycling', {}).get('vo2MaxValue')

            # Get training status
            training_status_data = training_status.get('mostRecentTrainingStatus', {}).get('latestTrainingStatusData', {})
            first_device = next(iter(training_status_data.values())) if training_status_data else {}
            training_status_phrase = first_device.get('trainingStatusFeedbackPhrase')

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
                all_activity_count=len(activities),
                running_activity_count=running_count,
                running_distance=running_distance,
                cycling_activity_count=cycling_count,
                cycling_distance=cycling_distance,
                strength_activity_count=strength_count,
                strength_duration=strength_duration,
                cardio_activity_count=cardio_count,
                cardio_duration=cardio_duration
            )

        except Exception as e:
            logger.error(f"Error fetching metrics for {target_date}: {str(e)}")
            # Return metrics object with just the date if there's an error
            return GarminMetrics(date=target_date)