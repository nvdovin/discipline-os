"""Pydantic request models. All user input passes through these validators."""

from __future__ import annotations

from datetime import date as DateType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIME_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToggleHabitIn(StrictModel):
    date: DateType | None = None
    completed: bool | None = None


class MealIn(StrictModel):
    date: DateType | None = None
    time: str | None = Field(default=None, pattern=TIME_PATTERN)
    description: str = Field(min_length=1, max_length=300)
    calories: int | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=500)
    carbs_g: float | None = Field(default=None, ge=0, le=500)
    fats_g: float | None = Field(default=None, ge=0, le=500)


class WaterIn(StrictModel):
    date: DateType | None = None
    amount_ml: int = Field(ge=50, le=3000)


class MeasurementIn(StrictModel):
    date: DateType | None = None
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    waist_cm: float | None = Field(default=None, ge=30, le=250)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def at_least_one(self) -> MeasurementIn:
        if self.weight_kg is None and self.waist_cm is None:
            raise ValueError("Укажите вес или обхват талии")
        return self


class SleepIn(StrictModel):
    date: DateType | None = None
    bedtime: str = Field(pattern=TIME_PATTERN)
    wake_up_time: str = Field(pattern=TIME_PATTERN)
    notes: str | None = Field(default=None, max_length=1000)


class BibleIn(StrictModel):
    date: DateType | None = None
    duration_minutes: int = Field(ge=1, le=600)
    notes: str | None = Field(default=None, max_length=2000)


class SecondaryTaskIn(StrictModel):
    id: str | None = Field(default=None, max_length=50)
    text: str = Field(min_length=1, max_length=200)
    done: bool = False


class PriorityIn(StrictModel):
    date: DateType | None = None
    main_priority: str | None = Field(default=None, max_length=300)
    priority_completed: bool | None = None
    secondary_tasks: list[SecondaryTaskIn] | None = Field(default=None, max_length=10)
    positive_result: str | None = Field(default=None, max_length=2000)
    difficulty: str | None = Field(default=None, max_length=2000)
    tomorrow_priority: str | None = Field(default=None, max_length=300)


class ExerciseSetIn(StrictModel):
    date: DateType | None = None
    exercise_key: str | None = Field(default=None, max_length=64)
    exercise_name: str | None = Field(default=None, max_length=120)
    repetitions: int | None = Field(default=None, ge=1, le=200)
    duration_seconds: int | None = Field(default=None, ge=1, le=7200)
    rest_seconds: int | None = Field(default=None, ge=0, le=600)
    mode: Literal["full", "minimum"] | None = None

    @model_validator(mode="after")
    def has_volume(self) -> ExerciseSetIn:
        if self.repetitions is None and self.duration_seconds is None:
            raise ValueError("Укажите повторения или длительность")
        if not self.exercise_key and not self.exercise_name:
            raise ValueError("Укажите упражнение")
        return self


class CompleteWorkoutIn(StrictModel):
    date: DateType | None = None
    mode: Literal["full", "minimum"] = "full"
    completed: bool = True
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    notes: str | None = Field(default=None, max_length=1000)


class RepTargetIn(StrictModel):
    sets: int = Field(ge=1, le=10)
    reps: int = Field(ge=1, le=100)


class DurationTargetIn(StrictModel):
    sets: int = Field(ge=1, le=10)
    duration_seconds: int = Field(ge=5, le=7200)


class ExerciseTargetsIn(StrictModel):
    pushups: RepTargetIn | None = None
    pullups: RepTargetIn | None = None
    squats: RepTargetIn | None = None
    lunges: RepTargetIn | None = None
    plank: DurationTargetIn | None = None
    walk: DurationTargetIn | None = None
    mobility: DurationTargetIn | None = None
    stretch: DurationTargetIn | None = None


class ReminderIn(StrictModel):
    key: str = Field(min_length=1, max_length=32)
    time: str = Field(pattern=TIME_PATTERN)
    enabled: bool = True


class SettingsIn(StrictModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    wake_up_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    bedtime: str | None = Field(default=None, pattern=TIME_PATTERN)
    meal_times: list[str] | None = Field(default=None, min_length=1, max_length=4)
    protein_target_g: int | None = Field(default=None, ge=40, le=300)
    water_target_ml: int | None = Field(default=None, ge=500, le=6000)
    bible_target_minutes: int | None = Field(default=None, ge=5, le=240)
    exercise_targets: ExerciseTargetsIn | None = None
    reminders: list[ReminderIn] | None = Field(default=None, max_length=20)

    @field_validator("meal_times")
    @classmethod
    def validate_meal_times(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        import re

        for item in value:
            if not re.fullmatch(TIME_PATTERN, item):
                raise ValueError("Время приёма должно быть в формате ЧЧ:ММ")
        if len(set(value)) != len(value):
            raise ValueError("Время приёмов не должно повторяться")
        return value

    @field_validator("reminders")
    @classmethod
    def unique_reminders(cls, value: list[ReminderIn] | None) -> list[ReminderIn] | None:
        if value is None:
            return value
        keys = [item.key for item in value]
        if len(set(keys)) != len(keys):
            raise ValueError("Напоминания не должны повторяться")
        return value
