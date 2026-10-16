import os
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


ShortText = Annotated[str, Field(min_length=1, max_length=200)]


class Empty(Arguments):
    pass


class ExchangeSearchArgs(Arguments):
    query: str = Field(default="", max_length=160)
    category: Literal["equipment", "labour", "transport", "produce"] | None = None
    kind: Literal["offer", "request"] | None = None
    state: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    mine: bool = False


class ExchangeMatchArgs(Arguments):
    listing_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


class SkillArgs(Arguments):
    skill: ShortText


class HistoryArgs(Arguments):
    hours: int = Field(default=24, ge=1, le=168)


class WeatherForecastArgs(Arguments):
    days: int = Field(default=7, ge=1, le=16)
    farm_key: str = Field(default="", max_length=100)


class WeatherArchiveArgs(Arguments):
    days: int = Field(default=30, ge=1, le=366)
    farm_key: str = Field(default="", max_length=100)


class CityWeatherArgs(Arguments):
    city: str = Field(min_length=2, max_length=100, description="City name; add state or country after a comma if ambiguous")
    days: int = Field(default=7, ge=1, le=10)


class MarketArgs(Arguments):
    commodity: ShortText
    state: str = Field(default="", max_length=100)
    market: str = Field(default="", max_length=100)


class ReportedMarketArgs(MarketArgs):
    observed_only: bool = Field(
        default_factory=lambda: os.environ.get("SKYVIEW_LOCAL_PRESENTATION") != "1",
        description="Require reported market observations; never substitute generated prices.",
    )


class MarketTrendArgs(ReportedMarketArgs):
    days: int | None = Field(
        default=None,
        ge=2,
        le=1095,
        description="Requested lookback ending today; omit for all available history.",
    )


class ResearchArgs(Arguments):
    query: str = Field(min_length=1, max_length=1200)
    language: str = Field(default="en", max_length=12)

    @field_validator("language")
    @classmethod
    def validate_language(cls, value):
        from skyview.languages import normalize_language

        return normalize_language(value)


class KnowledgeArgs(Arguments):
    query: ShortText
    language: str = Field(default="", max_length=12)
    limit: int = Field(default=5, ge=1, le=8)


class PriceScenarioArgs(MarketArgs):
    market: str = Field(default="", max_length=100)
    days: int = Field(default=365, ge=1, le=365)


class SchemeArgs(Arguments):
    state: str = Field(default="", max_length=100)
    query: str = Field(default="", max_length=100)


class QuestionField(Arguments):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: ShortText
    type: Literal["text", "number", "select", "date", "photo"] = "text"
    options: list[ShortText] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_options(self):
        if self.type == "select" and len(set(self.options)) < 2:
            raise ValueError("A selection field needs at least two distinct options")
        return self


class QuestionArgs(Arguments):
    question: ShortText
    fields: list[QuestionField] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({f.id for f in self.fields}) != len(self.fields):
            raise ValueError("Question fields must have distinct IDs")
        return self


class TaskArgs(Arguments):
    title: ShortText
    due_date: date
    notes: str = Field(default="", max_length=2000)


class CompleteTaskArgs(Arguments):
    task_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class FileReadArgs(Arguments):
    file_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class ExpenseArgs(Arguments):
    description: ShortText
    amount: float = Field(gt=0, le=100000000)
    date: date


class BudgetItem(Arguments):
    name: ShortText
    quantity: float = Field(ge=0, le=100000000)
    unit_price: float = Field(ge=0, le=100000000)


class BudgetArgs(Arguments):
    items: list[BudgetItem] = Field(min_length=1, max_length=100)


class Section(Arguments):
    heading: ShortText
    text: str = Field(min_length=1, max_length=5000)


class FileArgs(Arguments):
    format: Literal["docx", "pdf", "xlsx", "csv", "pptx"]
    title: ShortText
    sections: list[Section] = Field(default_factory=list, max_length=20)
    columns: list[ShortText] = Field(default_factory=list, max_length=15)
    rows: list[list[str | float | int | None]] = Field(
        default_factory=list, max_length=500
    )

    @model_validator(mode="after")
    def bounded_cells(self):
        if any(len(row) > 15 for row in self.rows):
            raise ValueError("A record can have at most 15 cells")
        if any(isinstance(v, str) and len(v) > 4000 for row in self.rows for v in row):
            raise ValueError("Each text cell must be at most 4000 characters")
        if sum(len(str(v)) for row in self.rows for v in row) > 200000:
            raise ValueError("Table text exceeds the document size limit")
        return self


class ReviseFileArgs(FileArgs):
    file_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class NetSaleArgs(Arguments):
    quantity_quintals: float = Field(gt=0, le=10000000)
    price_per_quintal: float = Field(gt=0, le=100000000)
    transport_cost: float = Field(default=0, ge=0, le=100000000)
    handling_cost: float = Field(default=0, ge=0, le=100000000)
    commission_percent: float = Field(default=0, ge=0, le=100)
    other_cost: float = Field(default=0, ge=0, le=100000000)


class RunRequest(Arguments):
    attachment_ids: list[Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]] = Field(
        default_factory=list, max_length=5
    )
    mission_id: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    )
    workspace_view: Literal[
        "assistant", "station", "calendar", "crops", "markets", "schemes", "records", "weather"
    ] = "assistant"
    selected_date: date | None = None
    weather_city: str | None = Field(default=None, max_length=160)
    message: str = Field(default="", max_length=6000)
    station_id: str = Field(default="WS01", pattern=r"^[A-Za-z0-9_-]{1,50}$")
    language: str | None = Field(default=None, max_length=12)

    @field_validator("language")
    @classmethod
    def supported_language(cls, value):
        from skyview.languages import normalize_language

        return normalize_language(value) if value else None

    answers: dict[str, str] | None = None
    approval: bool | None = None
    pending_id: str | None = None


class RecallArgs(Arguments):
    query: ShortText


class TaskPatch(TaskArgs):
    completed: bool | None = None
    row_version: int | None = Field(default=None, ge=1)


class UpdateTaskArgs(TaskPatch):
    task_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class EncodedAttachment(Arguments):
    filename: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=4, max_length=6990508)


class LedgerArgs(Arguments):
    description: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    kind: Literal["income", "expense"]
    basis: Literal["actual", "estimated", "receivable"]
    amount_inr: Decimal = Field(gt=0, le=100000000, max_digits=14, decimal_places=2)
    occurred_on: date
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def accounting_basis(self):
        if self.basis == "receivable" and self.kind != "income":
            raise ValueError("Only income can be a receivable")
        if (
            self.basis == "actual"
            and self.occurred_on > datetime.now(ZoneInfo("Asia/Kolkata")).date()
        ):
            raise ValueError(
                "An actual payment or expense cannot be dated in the future"
            )
        return self


class CaseArgs(Arguments):
    title: str = Field(min_length=2, max_length=160)
    note: str = Field(default="", max_length=4000)


class CaseNoteArgs(Arguments):
    case_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    note: str = Field(min_length=1, max_length=4000)
    observed_on: date


class MissionStep(Arguments):
    title: str = Field(min_length=1, max_length=160)
    done: Literal[False] = False


class MissionArgs(Arguments):
    title: str = Field(min_length=2, max_length=160)
    objective: str = Field(default="", max_length=2000)
    steps: list[MissionStep] = Field(min_length=1, max_length=30)


class ServiceArgs(Arguments):
    title: str = Field(min_length=2, max_length=160)
    service_type: Literal["labour", "machinery", "transport", "expert", "other"]
    supplier: str = Field(default="", max_length=160)
    quote_inr: Decimal | None = Field(
        default=None, ge=0, le=100000000, max_digits=14, decimal_places=2
    )
    scheduled_on: date | None = None
    notes: str = Field(default="", max_length=2000)
    status: Literal[
        "planned",
        "requested",
        "quote_recorded",
        "farmer_confirmed",
        "farmer_completed",
        "cancelled",
    ] = "planned"


class GroupArgs(Arguments):
    name: str = Field(min_length=2, max_length=100)


class GroupReadArgs(Arguments):
    group_id: str = Field(
        pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
    )


class GroupTaskArgs(GroupReadArgs):
    title: str = Field(min_length=2, max_length=160)
    notes: str = Field(default="", max_length=2000)
    due_on: date | None = None


class SoilReportValue(Arguments):
    property: Literal[
        "ph",
        "organic_carbon",
        "nitrogen",
        "phosphorus",
        "potassium",
        "sulphur",
        "zinc",
        "iron",
        "copper",
        "manganese",
        "boron",
        "ec",
    ]
    unit_code: str = Field(min_length=1, max_length=20)
    value: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    reported_basis: str = Field(min_length=3, max_length=160)
    depth_top_cm: Decimal = Field(ge=0, lt=200, max_digits=6, decimal_places=2)
    depth_bottom_cm: Decimal = Field(gt=0, le=200, max_digits=6, decimal_places=2)


class SaveSoilArgs(Arguments):
    plot_id: str = Field(
        pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
    )
    attachment_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    sampled_on: date
    values: list[SoilReportValue] = Field(min_length=1, max_length=36)
    reported_lab_name: str | None = Field(default=None, max_length=160)


class SeasonalPlanningArgs(Arguments):
    start_month: int = Field(default=1, ge=1, le=12)
    end_month: int = Field(default=3, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=2100)
    state: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    soil_texture: str = Field(default="", max_length=120)
    water_availability: str = Field(default="", max_length=250)
    crop_names: list[ShortText] = Field(default_factory=list, max_length=8)
    language: str = Field(default="", max_length=12)
