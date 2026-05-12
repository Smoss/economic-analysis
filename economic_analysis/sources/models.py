from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class BlsObservation(SourceModel):
    year: str
    period: str
    value: str | None = None
    period_name: str | None = Field(default=None, validation_alias=AliasChoices("periodName", "period_name"))
    footnotes: list[dict[str, Any]] = Field(default_factory=list)


class BlsSeries(SourceModel):
    series_id: str = Field(validation_alias=AliasChoices("seriesID", "series_id"))
    data: list[BlsObservation] = Field(default_factory=list)


class BlsResults(SourceModel):
    series: list[BlsSeries] = Field(default_factory=list)


class BlsLaborResponse(SourceModel):
    status: str | None = None
    response_time: int | None = Field(default=None, validation_alias=AliasChoices("responseTime", "response_time"))
    message: list[str] = Field(default_factory=list)
    results: BlsResults = Field(default_factory=BlsResults, validation_alias=AliasChoices("Results", "results"))


class NormalizedLaborRow(BaseModel):
    date: str
    series_id: str
    survey: str | None
    measure: str
    value: float | None
    unit: str | None
    frequency: Literal["monthly"]
    seasonality: Literal["seasonally_adjusted"]


class NormalizedCexConsumptionRow(BaseModel):
    year: int
    period: str
    frequency: Literal["annual"]
    series_id: str
    category: str
    subcategory: str | None
    item: str | None
    demographic: Literal["income_quintile"]
    group: str
    measure: Literal["aggregate_expenditure"]
    value: float | None
    unit: Literal["millions_of_dollars"]
    raw_aspect_value: float | None
    raw_aspect_unit: Literal["percent_of_total_aggregate"]
    footnote_code: str | None


class BeaError(SourceModel):
    api_error_code: str | None = Field(default=None, validation_alias=AliasChoices("APIErrorCode", "api_error_code"))
    api_error_description: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APIErrorDescription", "api_error_description"),
    )


class BeaNote(SourceModel):
    note_ref: str | None = Field(default=None, validation_alias=AliasChoices("NoteRef", "note_ref"))
    note_text: str | None = Field(default=None, validation_alias=AliasChoices("NoteText", "note_text"))


class BeaPceDataRow(SourceModel):
    time_period: str = Field(validation_alias=AliasChoices("TimePeriod", "time_period"))
    data_value: str | None = Field(default=None, validation_alias=AliasChoices("DataValue", "data_value"))
    line_number: str | None = Field(default=None, validation_alias=AliasChoices("LineNumber", "Line", "line_number"))
    line_description: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LineDescription", "Description", "SeriesDescription", "line_description"),
    )
    unit: str | None = Field(default=None, validation_alias=AliasChoices("UNIT_MULT", "Unit", "CL_UNIT", "unit"))
    table_name: str | None = Field(default=None, validation_alias=AliasChoices("TableName", "table_name"))


class BeaGdpComponentDataRow(SourceModel):
    time_period: str = Field(validation_alias=AliasChoices("TimePeriod", "time_period"))
    data_value: str | None = Field(default=None, validation_alias=AliasChoices("DataValue", "data_value"))
    line_number: str | None = Field(default=None, validation_alias=AliasChoices("LineNumber", "Line", "line_number"))
    line_description: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LineDescription", "Description", "SeriesDescription", "line_description"),
    )
    unit: str | None = Field(default=None, validation_alias=AliasChoices("UNIT_MULT", "Unit", "CL_UNIT", "unit"))
    table_name: str | None = Field(default=None, validation_alias=AliasChoices("TableName", "table_name"))


class BeaGdpIndustryDataRow(SourceModel):
    year: str | int | None = Field(default=None, validation_alias=AliasChoices("Year", "TimePeriod", "year"))
    quarter: str | int | None = Field(default=None, validation_alias=AliasChoices("Quarter", "quarter"))
    frequency: str | None = Field(default=None, validation_alias=AliasChoices("Frequency", "frequency"))
    industry: str | None = Field(default=None, validation_alias=AliasChoices("Industry", "IndustrY", "industry"))
    industry_description: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "IndustrYDescription", "IndustryDescription", "Description", "industry_description"
        ),
    )
    data_value: str | None = Field(default=None, validation_alias=AliasChoices("DataValue", "data_value"))
    unit: str | None = Field(default=None, validation_alias=AliasChoices("Unit", "UNIT_MULT", "unit"))
    table_id: str | None = Field(default=None, validation_alias=AliasChoices("TableID", "table_id"))


class BeaResultBlock(SourceModel):
    data: list[dict[str, Any]] = Field(default_factory=list, validation_alias=AliasChoices("Data", "data"))
    notes: list[BeaNote | dict[str, Any]] = Field(default_factory=list, validation_alias=AliasChoices("Notes", "notes"))


class BeaApiBody(SourceModel):
    results: BeaResultBlock | list[BeaResultBlock] = Field(
        default_factory=BeaResultBlock,
        validation_alias=AliasChoices("Results", "results"),
    )
    error: BeaError | dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices("Error", "error"))

    @model_validator(mode="after")
    def raise_for_api_error(self) -> BeaApiBody:
        if isinstance(self.error, BeaError) and (self.error.api_error_code or self.error.api_error_description):
            message = self.error.api_error_description or self.error.api_error_code
            raise ValueError(f"BEA API error: {message}")
        if self.error:
            raise ValueError(f"BEA API error: {self.error}")
        return self


class BeaResponse(SourceModel):
    beaapi: BeaApiBody = Field(validation_alias=AliasChoices("BEAAPI", "beaapi"))

    @property
    def result_blocks(self) -> list[BeaResultBlock]:
        results = self.beaapi.results
        return results if isinstance(results, list) else [results]

    def data_rows(self) -> list[dict[str, Any]]:
        return [row for result in self.result_blocks for row in result.data]

    def notes(self) -> list[BeaNote | dict[str, Any]]:
        return [note for result in self.result_blocks for note in result.notes]


class NormalizedPceRow(BaseModel):
    date: str | None
    frequency: Literal["monthly"]
    line_code: str | None
    category: str | None
    value: float | None
    unit: str | None
    source_table: str


class NormalizedGdpComponentRow(BaseModel):
    period: str
    year: int | None
    quarter: int | None
    frequency: Literal["annual", "quarterly"]
    component: str | None
    component_code: str
    value: float | None
    unit: str | None
    source_table: str


class NormalizedGdpIndustryRow(BaseModel):
    period: str
    year: int | None
    quarter: int | None
    frequency: Literal["annual", "quarterly"]
    industry: str | None
    industry_code: str | None
    metric: str
    value: float | None
    unit: str | None
    table_id: str


class ScfHomeAssetRow(BaseModel):
    survey_year: int
    asset_component: Literal["primary_residence", "other_residential_real_estate"]
    group_type: Literal["age", "education", "income", "net_worth_percentile", "race_ethnicity"]
    group: str
    statistic: Literal["have", "mean", "median"]
    value: float
    unit: Literal["percent_holding", "2022_dollars"]

    @field_validator("group")
    @classmethod
    def group_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("group must not be blank")
        return stripped
